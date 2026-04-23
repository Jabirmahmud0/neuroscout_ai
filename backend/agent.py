"""NeuroScout AI - Autonomous research agent.

ReAct-style loop: PLAN -> SEARCH -> FETCH -> REASON -> SYNTHESIZE.
Uses Gemini 3.1 Pro Preview and DuckDuckGo for web search.
Streams agent step events as JSON dicts for SSE.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

client = genai.Client(api_key=GEMINI_API_KEY)

MAX_SUBQUESTIONS = 5
MAX_RESULTS_PER_QUERY = 4
MAX_FETCH_CHARS = 4000
MAX_ITERATIONS_DEFAULT = 5


# --------------------------- Utility helpers --------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_code_fence(text: str) -> str:
    """Strip ```json ... ``` fences if the LLM wrapped JSON in them."""
    text = text.strip()
    if text.startswith("```"):
        # remove first line fence
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


def _safe_json(text: str) -> Optional[dict | list]:
    text = _strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try to extract first JSON object/array
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
        return None
    except Exception:
        return None


async def _fetch_page_text(url: str, client: httpx.AsyncClient) -> str:
    """Fetch a URL and return cleaned text up to MAX_FETCH_CHARS."""
    try:
        r = await client.get(url, follow_redirects=True, timeout=8.0,
                             headers={"User-Agent": "Mozilla/5.0 NeuroScout/1.0"})
        if r.status_code != 200 or not r.text:
            return ""
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:MAX_FETCH_CHARS]
    except Exception:
        return ""


def _ddg_search(query: str, max_results: int) -> List[Dict]:
    """Synchronous DuckDuckGo search; called via asyncio.to_thread."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="wt-wt"))
        # Normalize keys across ddgs versions
        normalized = []
        for r in results:
            normalized.append({
                "title": r.get("title") or r.get("heading") or "",
                "url": r.get("href") or r.get("url") or r.get("link") or "",
                "snippet": r.get("body") or r.get("snippet") or "",
            })
        return [r for r in normalized if r["url"]]
    except Exception:
        return []


# --------------------------- LLM helpers --------------------------- #

class SimpleChat:
    def __init__(self, model_name: str, system_message: str):
        self.model_name = model_name
        self.system_message = system_message

    async def send_message(self, text: str) -> str:
        # Running in executor as google-genai is sync
        loop = asyncio.get_event_loop()
        
        def _call():
            resp = client.models.generate_content(
                model=self.model_name,
                contents=text,
                config={
                    "system_instruction": self.system_message,
                }
            )
            return resp.text

        return await loop.run_in_executor(None, _call)

def _new_chat(session_id: str, system_message: str) -> SimpleChat:
    return SimpleChat(GEMINI_MODEL, system_message)


PLAN_SYSTEM = (
    "You are NeuroScout, an expert research planner. Given a user's research topic, "
    "decompose it into 3 to 5 concise, specific web search sub-questions that together "
    "would produce a comprehensive, balanced research report. Return ONLY a JSON array "
    "of strings, no commentary."
)

REASON_SYSTEM = (
    "You are NeuroScout, an expert research analyst. Given the original query, the list "
    "of sub-questions and the evidence collected so far, decide whether enough evidence "
    "exists to write a high-quality, balanced report. Respond with ONLY a JSON object: "
    '{"sufficient": true|false, "missing": "short description of what is still missing or empty string", '
    '"refined_query": "an additional search query to run if not sufficient, or empty string"}.'
)

SYNTHESIZE_SYSTEM = (
    "You are NeuroScout, an expert technical research writer. Using ONLY the provided "
    "evidence, write a structured research report. Every factual claim MUST cite at least "
    "one source by index using inline markers like [1] or [2,3] referring to the provided "
    "sources list (1-indexed). Be balanced and acknowledge uncertainty. If a sub-topic has "
    "no evidence, write 'Insufficient evidence found' for that section.\n\n"
    "Return ONLY a JSON object with this exact shape:\n"
    "{\n"
    '  "executive_summary": "3-5 sentence overview with citations like [1].",\n'
    '  "sections": [\n'
    '    {"heading": "Section title", "content": "Markdown content with inline [n] citations.", "source_ids": [1,2]}\n'
    "  ],\n"
    '  "key_takeaways": [\n'
    '    "Concise, actionable insight or key finding #1 (cite source if relevant, e.g. [1]).",\n'
    '    "Concise insight #2.",\n'
    '    "Concise insight #3."\n'
    "  ]\n"
    "}\n"
    "Use 3-6 sections. Each section's source_ids must be the 1-indexed source numbers actually cited in its content. "
    "Provide 3-5 key_takeaways: short, punchy bullet-style sentences summarising the most important conclusions for a reader in a hurry."
)


# --------------------------- Agent loop --------------------------- #

async def run_research(
    query: str,
    max_iterations: int = MAX_ITERATIONS_DEFAULT,
) -> AsyncGenerator[Dict, None]:
    """Run the autonomous research agent. Yields step event dicts.

    Final yielded event has type='final' with the full report payload.
    """
    if not GEMINI_API_KEY:
        yield {"type": "error", "ts": _now_iso(), "message": "GEMINI_API_KEY not configured"}
        return

    started = time.time()
    session_id = f"neuroscout-{uuid.uuid4()}"
    max_iterations = max(3, min(8, max_iterations))

    yield {"type": "start", "ts": _now_iso(), "query": query, "max_iterations": max_iterations}

    # ---------- PLAN ---------- #
    yield {"type": "plan", "ts": _now_iso(), "status": "running",
           "message": f"Decomposing query into sub-questions"}
    try:
        plan_chat = _new_chat(f"{session_id}-plan", PLAN_SYSTEM)
        plan_resp = await plan_chat.send_message(f"Research topic: {query}")
    except Exception as e:
        yield {"type": "error", "ts": _now_iso(), "message": f"Planner failed: {e}"}
        return

    sub_questions_raw = _safe_json(plan_resp)
    if not isinstance(sub_questions_raw, list) or not sub_questions_raw:
        sub_questions = [query]
    else:
        sub_questions = [str(s).strip() for s in sub_questions_raw if str(s).strip()][:MAX_SUBQUESTIONS]
    yield {"type": "plan", "ts": _now_iso(), "status": "done",
           "message": f"Planned {len(sub_questions)} sub-questions",
           "sub_questions": sub_questions}

    # ---------- SEARCH + FETCH iterations ---------- #
    sources: List[Dict] = []  # {url, title, content, sub_question}
    seen_urls: set[str] = set()

    iterations_used = 0
    queries_to_run: List[str] = list(sub_questions)

    async with httpx.AsyncClient() as http_client:
        while queries_to_run and iterations_used < max_iterations:
            sub_q = queries_to_run.pop(0)
            iterations_used += 1

            yield {"type": "search", "ts": _now_iso(), "status": "running",
                   "iteration": iterations_used, "query": sub_q,
                   "message": f"Searching: {sub_q}"}

            results = await asyncio.to_thread(_ddg_search, sub_q, MAX_RESULTS_PER_QUERY)

            yield {"type": "search", "ts": _now_iso(), "status": "done",
                   "iteration": iterations_used, "query": sub_q,
                   "results_count": len(results),
                   "results": [{"title": r["title"], "url": r["url"]} for r in results]}

            # Fetch top results in parallel
            new_results = [r for r in results if r["url"] not in seen_urls][:3]
            for r in new_results:
                seen_urls.add(r["url"])

            if new_results:
                yield {"type": "observe", "ts": _now_iso(), "status": "running",
                       "message": f"Reading {len(new_results)} pages"}
                fetched = await asyncio.gather(
                    *[_fetch_page_text(r["url"], http_client) for r in new_results]
                )
                for r, content in zip(new_results, fetched):
                    if content:
                        sources.append({
                            "url": r["url"],
                            "title": r["title"] or r["url"],
                            "content": content,
                            "snippet": r["snippet"],
                            "sub_question": sub_q,
                            "accessed_date": _now_iso(),
                        })
                yield {"type": "observe", "ts": _now_iso(), "status": "done",
                       "message": f"Captured {len([c for c in fetched if c])} pages",
                       "total_sources": len(sources)}

            # ---------- REASON: decide if more searching is needed ---------- #
            if iterations_used >= len(sub_questions) and iterations_used < max_iterations:
                yield {"type": "reason", "ts": _now_iso(), "status": "running",
                       "message": "Evaluating evidence sufficiency"}
                evidence_summary = "\n".join(
                    f"[{i+1}] {s['title']} ({s['url']}): {s['content'][:300]}..."
                    for i, s in enumerate(sources)
                )
                reason_prompt = (
                    f"Original query: {query}\n\nSub-questions: {json.dumps(sub_questions)}\n\n"
                    f"Evidence ({len(sources)} sources):\n{evidence_summary[:6000]}"
                )
                try:
                    reason_chat = _new_chat(f"{session_id}-reason-{iterations_used}", REASON_SYSTEM)
                    reason_resp = await reason_chat.send_message(reason_prompt)
                    decision = _safe_json(reason_resp) or {}
                except Exception as e:
                    decision = {"sufficient": True, "missing": "", "refined_query": ""}

                sufficient = bool(decision.get("sufficient", True))
                refined = str(decision.get("refined_query") or "").strip()
                missing = str(decision.get("missing") or "").strip()

                yield {"type": "reason", "ts": _now_iso(), "status": "done",
                       "sufficient": sufficient, "missing": missing,
                       "message": "Sufficient evidence" if sufficient else f"Need more: {missing or refined}"}

                if sufficient:
                    break
                if refined and refined not in seen_urls:
                    queries_to_run.append(refined)

    # ---------- SYNTHESIZE ---------- #
    if not sources:
        yield {"type": "error", "ts": _now_iso(),
               "message": "No sources retrieved. Web search returned nothing usable."}
        return

    yield {"type": "synthesize", "ts": _now_iso(), "status": "running",
           "message": f"Synthesizing report from {len(sources)} sources"}

    sources_block = "\n\n".join(
        f"SOURCE [{i+1}]\nTitle: {s['title']}\nURL: {s['url']}\nContent: {s['content'][:1800]}"
        for i, s in enumerate(sources)
    )
    synth_prompt = (
        f"<user_query>{query}</user_query>\n\n"
        f"<sub_questions>{json.dumps(sub_questions)}</sub_questions>\n\n"
        f"<sources>\n{sources_block}\n</sources>\n\n"
        "Write the structured JSON report now."
    )
    try:
        synth_chat = _new_chat(f"{session_id}-synth", SYNTHESIZE_SYSTEM)
        synth_resp = await synth_chat.send_message(synth_prompt)
    except Exception as e:
        yield {"type": "error", "ts": _now_iso(), "message": f"Synthesis failed: {e}"}
        return

    parsed = _safe_json(synth_resp)
    if not isinstance(parsed, dict) or "sections" not in parsed:
        # one retry
        try:
            retry_chat = _new_chat(f"{session_id}-synth-retry", SYNTHESIZE_SYSTEM)
            synth_resp = await retry_chat.send_message(
                synth_prompt + "\n\nIMPORTANT: Output must be ONLY valid JSON matching the schema."
            )
            parsed = _safe_json(synth_resp)
        except Exception:
            parsed = None

    if not isinstance(parsed, dict) or "sections" not in parsed:
        yield {"type": "error", "ts": _now_iso(), "message": "Failed to parse synthesized report"}
        return

    references = [
        {
            "id": i + 1,
            "title": s["title"],
            "url": s["url"],
            "accessed_date": s["accessed_date"],
        }
        for i, s in enumerate(sources)
    ]

    duration = round(time.time() - started, 2)
    report = {
        "report_id": str(uuid.uuid4()),
        "query": query,
        "executive_summary": parsed.get("executive_summary", ""),
        "sections": parsed.get("sections", []),
        "key_takeaways": parsed.get("key_takeaways", []),
        "references": references,
        "sub_questions": sub_questions,
        "search_iterations": iterations_used,
        "generation_time_sec": duration,
        "created_at": _now_iso(),
    }

    yield {"type": "synthesize", "ts": _now_iso(), "status": "done",
           "message": f"Report ready in {duration}s"}
    yield {"type": "final", "ts": _now_iso(), "report": report}
