"""NeuroScout AI - Autonomous research agent.

Upgraded research loop:
PLAN -> SEARCH -> FETCH -> EXTRACT -> CRITIQUE -> SYNTHESIZE -> POLISH
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

client: Optional[genai.Client] = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

MAX_SUBQUESTIONS = 5
MAX_RESULTS_PER_QUERY = 5
MAX_FETCH_CHARS = 5000
MAX_EVIDENCE_UNITS = 18
MAX_ITERATIONS_DEFAULT = 5
SEARCH_CACHE_TTL_SEC = 900
FETCH_CACHE_TTL_SEC = 1800

SOURCE_TYPE_WEIGHTS = {
    "research": 0.96,
    "clinical": 0.91,
    "official": 0.88,
    "educational": 0.84,
    "general": 0.65,
    "blog": 0.35,
}

SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
FETCH_CACHE: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _safe_json(text: str) -> Optional[dict | list]:
    text = _strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    except Exception:
        return None


def _cache_get(cache: Dict[str, Dict[str, Any]], key: str, ttl_sec: int) -> Optional[Any]:
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() - entry["ts"] > ttl_sec:
        cache.pop(key, None)
        return None
    return entry["value"]


def _cache_set(cache: Dict[str, Dict[str, Any]], key: str, value: Any) -> None:
    cache[key] = {"ts": time.time(), "value": value}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower())


def _keyword_pool(query: str, plan_items: List[Dict[str, Any]]) -> List[str]:
    tokens = _tokenize(query)
    for item in plan_items:
        tokens.extend(_tokenize(item.get("sub_question", "")))
        tokens.extend(_tokenize(" ".join(item.get("search_queries", []))))
    common = {
        "about",
        "their",
        "there",
        "which",
        "would",
        "could",
        "should",
        "what",
        "when",
        "where",
        "with",
        "from",
        "into",
        "than",
        "this",
        "that",
        "have",
        "will",
        "they",
        "them",
        "your",
        "query",
        "research",
        "topic",
    }
    counts = Counter(t for t in tokens if len(t) > 2 and t not in common)
    return [token for token, _ in counts.most_common(20)]


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _detect_source_type(url: str, title: str, snippet: str) -> str:
    host = _domain(url)
    text = f"{title} {snippet} {host}".lower()
    if any(x in text for x in ("journal", "pubmed", "doi.org", "ncbi.nlm.nih.gov", "study", "systematic review")):
        return "research"
    if any(x in host for x in ("nih.gov", "cdc.gov", "who.int", ".gov")):
        return "official"
    if any(x in host for x in (".edu",)):
        return "educational"
    if any(x in text for x in ("clinic", "hospital", "medline", "nhs", "mayoclinic", "clevelandclinic")):
        return "clinical"
    if any(x in text for x in ("blog", "medium.com", "substack", "opinion")):
        return "blog"
    return "general"


def _score_result(result: Dict[str, Any], query_terms: List[str]) -> float:
    hay = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    overlap = sum(1 for term in query_terms if term in hay)
    source_type = result.get("source_type", "general")
    quality = SOURCE_TYPE_WEIGHTS.get(source_type, 0.5)
    return round(min(0.99, quality * 0.7 + min(0.3, overlap * 0.03)), 3)


async def _fetch_page(url: str, client_: httpx.AsyncClient) -> Dict[str, Any]:
    cached = _cache_get(FETCH_CACHE, url, FETCH_CACHE_TTL_SEC)
    if cached is not None:
        return {**cached, "_cache_hit": True}
    try:
        response = await client_.get(
            url,
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0 NeuroScout/2.0"},
        )
        if response.status_code != 200 or not response.text:
            return {"url": url, "content": "", "status_code": response.status_code}
        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        paragraphs = []
        for element in soup.find_all(["p", "li", "blockquote"]):
            text = " ".join(element.get_text(separator=" ").split())
            if len(text) >= 80:
                paragraphs.append(text)
        content = "\n".join(paragraphs)[:MAX_FETCH_CHARS]
        payload = {"url": url, "title": title, "content": content, "status_code": response.status_code}
        _cache_set(FETCH_CACHE, url, payload)
        return {**payload, "_cache_hit": False}
    except Exception:
        payload = {"url": url, "content": "", "status_code": None}
        _cache_set(FETCH_CACHE, url, payload)
        return {**payload, "_cache_hit": False}


def _extract_evidence_units(
    page: Dict[str, Any],
    query_terms: List[str],
    sub_question: str,
    source_type: str,
    base_score: float,
) -> List[Dict[str, Any]]:
    paragraphs = [p.strip() for p in page.get("content", "").split("\n") if p.strip()]
    if not paragraphs:
        return []

    units = []
    for idx, paragraph in enumerate(paragraphs):
        lower = paragraph.lower()
        overlap = [term for term in query_terms if term in lower]
        if not overlap and idx >= 4:
            continue
        relevance = min(0.99, 0.25 + 0.08 * len(set(overlap)))
        confidence = min(0.99, SOURCE_TYPE_WEIGHTS.get(source_type, 0.5) * 0.75 + relevance * 0.25)
        units.append(
            {
                "excerpt": paragraph[:900],
                "relevance_score": round(relevance, 3),
                "confidence_score": round(confidence, 3),
                "matched_terms": sorted(set(overlap))[:8],
                "sub_question": sub_question,
                "source_quality_score": base_score,
            }
        )
    units.sort(key=lambda item: (item["relevance_score"], item["confidence_score"]), reverse=True)
    return units[:3]


def _summarize_evidence_units(sources: List[Dict[str, Any]]) -> str:
    lines = []
    for index, source in enumerate(sources, start=1):
        lines.append(
            f"[{index}] {source['title']} | type={source['source_type']} | "
            f"quality={source['source_quality_score']} | url={source['url']}"
        )
        for unit in source.get("evidence_units", [])[:2]:
            lines.append(
                f"  - q={unit['sub_question']} | rel={unit['relevance_score']} | conf={unit['confidence_score']} | "
                f"excerpt={unit['excerpt'][:260]}"
            )
    return "\n".join(lines)


def _top_references(sources: List[Dict[str, Any]], limit: int = 3) -> List[int]:
    ranked = sorted(
        enumerate(sources, start=1),
        key=lambda item: (
            item[1].get("source_quality_score", 0),
            max((u.get("confidence_score", 0) for u in item[1].get("evidence_units", [])), default=0),
        ),
        reverse=True,
    )
    return [idx for idx, _ in ranked[:limit]]


async def _search_for_high_authority_sources(
    query: str,
    keyword_pool: List[str],
    sources: List[Dict[str, Any]],
    seen_urls: set[str],
    http_client: httpx.AsyncClient,
    observer: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    extra_queries = [
        f"{query} research review official",
        f"{query} clinical guidance mechanism",
    ]
    for extra_query in extra_queries:
        raw_results = await asyncio.to_thread(_ddg_search, extra_query, MAX_RESULTS_PER_QUERY)
        ranked_results = []
        for result in raw_results:
            source_type = _detect_source_type(result["url"], result["title"], result["snippet"])
            if source_type not in HIGH_AUTHORITY_SOURCE_TYPES:
                continue
            score = _score_result({**result, "source_type": source_type}, keyword_pool)
            ranked_results.append({**result, "source_type": source_type, "source_quality_score": score})

        ranked_results.sort(key=lambda item: item["source_quality_score"], reverse=True)
        selected_results = []
        for result in ranked_results:
            normalized_url = _normalize_url(result["url"])
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            selected_results.append(result)
            if len(selected_results) >= 2:
                break

        if not selected_results:
            continue

        fetched_pages = await asyncio.gather(*[_fetch_page(r["url"], http_client) for r in selected_results])
        _emit(
            observer,
            "fetch_completed",
            fetched_count=len(fetched_pages),
            cache_hits=sum(1 for page in fetched_pages if page.get("_cache_hit")),
        )
        for result, page in zip(selected_results, fetched_pages):
            evidence_units = _extract_evidence_units(
                page,
                keyword_pool,
                "high_authority_follow_up",
                result["source_type"],
                result["source_quality_score"],
            )
            if not evidence_units:
                continue
            sources.append(
                {
                    "url": result["url"],
                    "title": page.get("title") or result["title"] or result["url"],
                    "snippet": result["snippet"],
                    "sub_question": "high_authority_follow_up",
                    "intent": "comparison",
                    "source_type": result["source_type"],
                    "source_quality_score": result["source_quality_score"],
                    "accessed_date": _now_iso(),
                    "evidence_units": evidence_units,
                }
            )
        sources = sorted(
            sources,
            key=lambda item: (
                item.get("source_quality_score", 0),
                max((u.get("confidence_score", 0) for u in item.get("evidence_units", [])), default=0),
            ),
            reverse=True,
        )[:MAX_EVIDENCE_UNITS]
        if _count_high_authority_sources(sources) >= 2:
            break
    return sources


def _default_plan(query: str) -> List[Dict[str, Any]]:
    return [
        {
            "sub_question": f"What is the clearest definition and framing of {query}?",
            "intent": "definition",
            "search_queries": [f"{query} definition overview", f"{query} explained"],
        },
        {
            "sub_question": f"What mechanisms or causes explain {query}?",
            "intent": "mechanism",
            "search_queries": [f"{query} causes mechanism", f"{query} why it happens"],
        },
        {
            "sub_question": f"What related conditions, systems, or comparisons matter for {query}?",
            "intent": "comparison",
            "search_queries": [f"{query} related conditions", f"{query} comparison"],
        },
    ]


def _count_high_authority_sources(sources: List[Dict[str, Any]]) -> int:
    return sum(1 for source in sources if source.get("source_type") in HIGH_AUTHORITY_SOURCE_TYPES)


def _used_domains(report: Dict[str, Any]) -> List[str]:
    text_parts = [report.get("executive_summary", ""), report.get("critical_insight", "")]
    text_parts.extend(section.get("content", "") for section in report.get("sections", []))
    hay = "\n".join(text_parts).lower()
    used = []
    for name, terms in DOMAIN_KEYWORDS.items():
        if any(term in hay for term in terms):
            used.append(name)
    return used


def check_causal_chain(report: Dict[str, Any]) -> bool:
    """Require multi-step causal chains, not single-step explanations."""
    text = "\n".join(section.get("content", "") for section in report.get("sections", []))
    text = f"{text}\n{report.get('critical_insight', '')}".lower()
    if not any(marker in text for marker in CAUSAL_CHAIN_MARKERS):
        return False
    # Check for multi-step: at least 2 chain markers in the same text block
    chain_count = sum(1 for marker in CAUSAL_CHAIN_MARKERS if marker in text)
    return chain_count >= 2


def check_mechanism_depth(report: Dict[str, Any]) -> bool:
    sections_text = " ".join(section.get("content", "") for section in report.get("sections", [])).lower()
    has_cause = any(marker in sections_text for marker in ("because", "due to", "driven by", "caused by"))
    has_process = any(marker in sections_text for marker in MECHANISM_MARKERS)
    has_effect = any(marker in sections_text for marker in ("therefore", "results in", "leads to", "outcome", "behavior"))
    return has_cause and has_process and has_effect


def check_cross_domain(report: Dict[str, Any]) -> bool:
    return len(_used_domains(report)) >= 2


def check_strong_sources(references: List[Dict[str, Any]]) -> bool:
    """Require 2+ high-authority sources AND no more than 50% general sources."""
    high_count = sum(1 for ref in references if ref.get("source_type") in HIGH_AUTHORITY_SOURCE_TYPES)
    general_count = sum(1 for ref in references if ref.get("source_type") in {"general", "blog"})
    total = len(references)
    if total == 0:
        return False
    return high_count >= 2 and (general_count / total) <= 0.5


def check_behavioral_economics(report: Dict[str, Any], query: str) -> bool:
    """Require at least 2 DIFFERENT behavioral biases/concepts when topic is behavioral."""
    query_tokens = set(_tokenize(query))
    needs_behavioral_econ = bool(query_tokens & DECISION_KEYWORDS)
    if not needs_behavioral_econ:
        return True
    text = "\n".join(
        [report.get("executive_summary", ""), report.get("critical_insight", "")]
        + [section.get("content", "") for section in report.get("sections", [])]
    ).lower()
    found_terms = sum(1 for term in BEHAVIORAL_ECON_TERMS if term in text)
    return found_terms >= 2  # Require 2+ different biases, not just 1


def check_human_reality_layer(report: Dict[str, Any], query: str) -> bool:
    """Check that the report includes real-world behavioral drivers when relevant."""
    query_tokens = set(_tokenize(query))
    behavioral_topic = bool(query_tokens & (DECISION_KEYWORDS | {"social", "media", "internet", "gaming", "shopping", "eating"}))
    if not behavioral_topic:
        return True
    text = "\n".join(
        [report.get("executive_summary", ""), report.get("critical_insight", "")]
        + [section.get("content", "") for section in report.get("sections", [])]
    ).lower()
    return any(term in text for term in HUMAN_REALITY_TERMS)


def check_required_sections(report: Dict[str, Any]) -> bool:
    """Check that the report includes all required section types."""
    headings = [section.get("heading", "").lower() for section in report.get("sections", [])]
    all_headings = " ".join(headings)
    found = set()
    for category, keywords in REQUIRED_SECTION_KEYWORDS.items():
        if any(kw in all_headings for kw in keywords):
            found.add(category)
    return len(found) >= 3  # At least 3 of 4 required section types


def check_evidence_gap_depth(report: Dict[str, Any]) -> bool:
    """Check that evidence gaps have structured detail (what, why, needed)."""
    gaps = report.get("evidence_gaps", [])
    if not gaps:
        return False
    if isinstance(gaps[0], dict):
        return all(
            g.get("gap") and g.get("reason") and g.get("needed")
            for g in gaps
        )
    # Accept string-format gaps as partial pass
    return len(gaps) >= 1


def check_insight_quality(report: Dict[str, Any]) -> bool:
    """Insight must be non-obvious, cross-domain, unique, and simple enough for a non-expert."""
    insight = (report.get("critical_insight") or "").strip()
    if len(insight) < 40:
        return False
    # Reject generic insights
    if any(phrase in insight.lower() for phrase in ("people avoid discomfort", "primitive threat response", "things are complex")):
        return False
    # Must not be a copy of earlier section content
    prior_text = " ".join(section.get("content", "") for section in report.get("sections", [])).lower()
    insight_lower = insight.lower()
    if insight_lower and insight_lower in prior_text:
        return False
    # Simplicity gate: must be expressible in roughly one sentence (under 400 chars)
    if len(insight) > 400:
        return False
    return check_cross_domain({"executive_summary": "", "critical_insight": insight, "sections": []}) or any(
        marker in insight_lower for marker in ("counterintuitive", "paradox", "not because", "rather than", "misunderstand", "actually", "surprising")
    )


def check_real_world_examples(report: Dict[str, Any]) -> bool:
    """Check that the report includes concrete real-world behavioral examples."""
    text = "\n".join(
        [report.get("executive_summary", "")]
        + [section.get("content", "") for section in report.get("sections", [])]
    ).lower()
    example_markers = (
        "for example", "for instance", "such as", "e.g.",
        "consider a", "consider when", "consider how",
        "imagine a", "real-world", "in practice",
        "everyday", "common example", "when someone", "when people",
        "scrolling through", "checking your", "holding a losing",
        "buying", "shopping", "at the store", "on social media",
        "at work", "in relationships", "eating", "drinking",
        "procrastinat", "quitting near", "avoiding opportunit",
        "before a deadline", "before an exam", "before an interview",
    )
    return any(marker in text for marker in example_markers)


def check_identity_feedback_loop(report: Dict[str, Any], query: str) -> bool:
    """Check for identity -> behavior -> outcome -> identity reinforcement loop when relevant."""
    query_lower = query.lower()
    identity_topics = ("self-sabotage", "sabotage", "failure", "self-defeat", "self-destruct",
                       "repeated failure", "pattern", "cycle", "keep failing", "always fail",
                       "imposter", "self-worth", "self-esteem", "identity")
    needs_identity = any(t in query_lower for t in identity_topics)
    if not needs_identity:
        return True
    text = "\n".join(
        [report.get("executive_summary", ""), report.get("critical_insight", "")]
        + [section.get("content", "") for section in report.get("sections", [])]
    ).lower()
    identity_markers = (
        "identity", "self-concept", "self-image", "self-belief",
        "identity reinforcement", "identity feedback",
        "self-fulfilling", "internalized", "self-schema",
        "i am not", "i am a failure", "belief about oneself",
    )
    return sum(1 for m in identity_markers if m in text) >= 2


def check_escalation_pattern(report: Dict[str, Any], query: str) -> bool:
    """Check for escalation patterns (small avoidance -> repeated delay -> major self-sabotage)."""
    query_lower = query.lower()
    escalation_topics = ("sabotage", "avoidance", "procrastinat", "delay", "self-control",
                         "addiction", "compulsive", "habit", "cycle", "pattern")
    needs_escalation = any(t in query_lower for t in escalation_topics)
    if not needs_escalation:
        return True
    text = "\n".join(
        [section.get("content", "") for section in report.get("sections", [])]
    ).lower()
    escalation_markers = (
        "escalat", "small", "minor", "gradually", "over time",
        "repeated", "accumulate", "spiral", "snowball",
        "starts with", "begins with", "initially",
        "short-term relief", "temporary relief", "immediate relief",
        "habit formation", "behavior repetition", "reinforcement loop",
    )
    return sum(1 for m in escalation_markers if m in text) >= 3


def validate_output(report: Dict[str, Any], references: List[Dict[str, Any]], query: str) -> Dict[str, bool]:
    return {
        "has_causal_chain": check_causal_chain(report),
        "has_cross_domain": check_cross_domain(report),
        "has_mechanism_depth": check_mechanism_depth(report),
        "has_strong_sources": check_strong_sources(references),
        "has_insight_quality": check_insight_quality(report),
        "has_behavioral_economics": check_behavioral_economics(report, query),
        "has_human_reality_layer": check_human_reality_layer(report, query),
        "has_required_sections": check_required_sections(report),
        "has_evidence_gap_depth": check_evidence_gap_depth(report),
        "has_real_world_examples": check_real_world_examples(report),
        "has_identity_loop": check_identity_feedback_loop(report, query),
        "has_escalation_pattern": check_escalation_pattern(report, query),
    }


class SimpleChat:
    def __init__(self, model_name: str, system_message: str):
        self.model_name = model_name
        self.system_message = system_message

    async def send_message(self, text: str) -> str:
        loop = asyncio.get_event_loop()

        def _call():
            if client is None:
                raise ValueError("GEMINI_API_KEY not configured")
            resp = client.models.generate_content(
                model=self.model_name,
                contents=text,
                config={"system_instruction": self.system_message},
            )
            return resp.text

        return await loop.run_in_executor(None, _call)


def _new_chat(system_message: str) -> SimpleChat:
    return SimpleChat(GEMINI_MODEL, system_message)


def _emit(observer: Optional[Callable[[str, Dict[str, Any]], None]], event: str, **payload: Any) -> None:
    if observer is None:
        return
    try:
        observer(event, payload)
    except Exception:
        pass


PLAN_SYSTEM = """
You are NeuroScout's research planner.

Given a user query and research mode, produce 4 to 6 distinct planning objects.
Each object must cover a different dimension of the topic.
The plan MUST include these intent categories when relevant:
- definition
- mechanism
- comparison
- debate
- edge_case

Return ONLY valid JSON with this exact shape:
[
  {
    "sub_question": "specific analytical question",
    "intent": "definition | mechanism | comparison | debate | edge_case",
    "search_queries": ["query 1", "query 2"]
  }
]

Rules:
- Avoid overlap between sub_questions.
- search_queries must be concrete, web-searchable, and diversified.
- Prefer wording that can retrieve primary, official, clinical, or research sources.
- Use the research mode to adjust depth, but never drop core coverage.
"""

REASON_SYSTEM = """
You are NeuroScout's critic. Review the evidence gathered so far and decide what is still missing.

Return ONLY valid JSON with this shape:
{
  "sufficient": true,
  "missing_aspects": ["..."],
  "weak_points": ["..."],
  "conflicts": [
    {
      "topic": "...",
      "source_a": 1,
      "source_b": 2,
      "summary": "brief explanation of the disagreement"
    }
  ],
  "new_queries": ["..."],
  "confidence_summary": "low | medium | high"
}

Rules:
- If the explanation lacks mechanism, nuance, comparisons, or conflicting viewpoints, mark it insufficient.
- Generate targeted new_queries only for missing evidence.
- Keep conflict entries grounded in the provided source ids.
"""

SYNTHESIZE_SYSTEM = """
You are NeuroScout's synthesis engine. Use ONLY the provided evidence.

Return ONLY valid JSON with this exact shape:
{
  "executive_summary": "3-5 sentence overview with inline citations like [1].",
  "sections": [
    {
      "heading": "Section title",
      "content": "Markdown with inline citations. Each section MUST include: WHY it happens (cause), HOW it works (process), and WHAT it leads to (effect).",
      "source_ids": [1, 2]
    }
  ],
  "critical_insight": "One non-obvious, cross-domain conclusion in ONE clear sentence a non-expert can understand. Must connect 2+ domains. Must NOT repeat earlier sections. Think 'dinner party insight' — sharp, memorable, surprising.",
  "common_misconceptions": [
    "Misconception corrected with citations."
  ],
  "conflicting_evidence": [
    {
      "topic": "short label",
      "summary": "Explain the conflict and likely reason with citations.",
      "source_ids": [1, 2]
    }
  ],
  "evidence_gaps": [
    {
      "gap": "What is missing",
      "reason": "Why it is missing",
      "needed": "What research or data would be needed"
    }
  ],
  "confidence_summary": {
    "overall": "low | medium | high",
    "rationale": "Why that confidence level is appropriate."
  },
  "key_takeaways": [
    "Short actionable takeaway with citations."
  ]
}

MANDATORY SECTION STRUCTURE - You MUST include these sections in order:
1. "Neurological Mechanisms" - brain regions, neurotransmitters, neural pathways involved
2. "Psychological Mechanisms" - cognitive processes, mental models, psychological theories
3. "Behavioral Reinforcement Mechanisms" - MUST include:
   - habit loop (cue -> action -> reward) and/or reward dynamics
   - At least TWO of: loss aversion, sunk cost fallacy, confirmation bias, framing effect, self-handicapping, status quo bias, endowment effect
   - Social proof and framing effects on decision-making
   - Reinforcement schedules, conditioning patterns
   - ESCALATION PATTERN: Show how small avoidance -> repeated delay -> major self-sabotage. Include short-term relief -> behavior repetition -> habit formation.
4. "Cross-Domain Mechanism Chain" - MUST connect at least 2 domains (e.g. neuroscience + economics). Include at least one explicit MULTI-STEP causal chain using A -> B -> C -> D -> Outcome format (minimum 3 intermediate steps).

Additional sections are allowed and encouraged based on the topic.

IDENTITY FEEDBACK LOOP (MANDATORY for self-sabotage, failure patterns, repeated cycles):
If the topic involves self-sabotage, repeated failure, or behavioral cycles, you MUST model:
identity -> behavior -> outcome -> identity reinforcement
Example: "A person who believes they are 'not good enough' (identity) avoids preparing for a presentation (behavior), performs poorly (outcome), which confirms their belief that they are incompetent (identity reinforcement), creating a self-perpetuating cycle."

BEHAVIORAL ECONOMICS AUTO-DETECT:
If the query involves decision-making, motivation, delay, avoidance, reward, addiction, self-control, or self-sabotage:
- You MUST include at least TWO DIFFERENT behavioral biases from: present bias, temporal discounting, loss aversion, sunk cost fallacy, confirmation bias, framing effect, self-handicapping, anchoring, status quo bias
- When the topic involves self-control, avoidance, or delayed outcomes: MUST include temporal discounting or present bias
- CRITICAL: Include the most relatable, well-known biases (loss aversion, sunk cost, confirmation bias) alongside technical ones. Do NOT only pick academic terms.

HUMAN REALITY LAYER:
Where relevant, you MUST include real-world behavioral drivers:
- social validation and peer influence
- FOMO (fear of missing out)
- social comparison mechanisms
- emotional regulation loops
MUST include concrete real-world patterns such as:
- procrastination before important events (exams, deadlines, interviews)
- quitting or self-sabotaging near success
- avoiding high-stakes opportunities
Integrate these into the Psychological or Behavioral sections rather than listing them separately.

REAL-WORLD GROUNDING (MANDATORY):
Every behavioral section MUST include at least one CONCRETE real-world example that a non-expert would immediately recognize. Use phrases like "for example", "consider when someone", "in everyday life".
Examples of good grounding:
- "For example, a student who procrastinates before an exam to protect their ego — if they fail, they can blame the lack of preparation rather than their ability (self-handicapping)"
- "Consider someone who keeps checking their phone despite wanting to focus — each notification provides a small dopamine hit (variable reward schedule) while the important task offers only delayed, uncertain reward (temporal discounting)"

CAUSAL CHAIN REQUIREMENT:
At least one section MUST include an explicit MULTI-STEP causal chain formatted as:
A -> B -> C -> D -> Outcome
Where each step is a distinct mechanism. Single-step explanations like "stress -> bad decision" are NOT sufficient.
Example: "low self-worth (identity) -> fear of exposure (psychological) -> avoidance of preparation (behavioral) -> poor performance (outcome) -> reinforced belief of incompetence (identity loop)"

MECHANISM DEPTH:
Each major section MUST include:
- WHY it happens (cause)
- HOW it works (process)
- WHAT it leads to (effect)

INSIGHT SIMPLICITY RULE:
The critical_insight MUST be:
- ONE clear sentence a non-expert can understand
- Mechanism-focused (explains WHY, not just WHAT)
- Non-obvious and generalizable across contexts
- AVOID: poetic language, vague metaphors, dense jargon
- GOOD: "People self-sabotage not despite wanting success, but because succeeding would force them to update a self-concept they've built their entire coping strategy around [1,3]."
- BAD: "The tapestry of neural cascades weaves a paradoxical dance of self-destruction."

CLARITY OPTIMIZATION:
- Use simple, direct language when possible. Prefer "because" over "due to the fact that".
- Maintain depth but improve readability. Every sentence should earn its complexity.
- If a simpler word conveys the same meaning, use it. "fear" over "apprehension", "brain" over "cerebral architecture".
- Technical terms are fine when they add precision, but always follow them with a brief plain-language explanation.

Rules:
- Do not summarize source-by-source. Merge ideas across sources.
- Every factual claim must use inline citations like [1] or [2,3].
- No generic explanations. No shallow summaries. All points must be explained or connected.
- If sources disagree, surface that in conflicting_evidence instead of smoothing it away.
- For each evidence gap: state what is missing, why it is missing, and what research would be needed.
- Connect theory to recognizable human behavior. The reader should think "that's exactly what I do".
"""

POLISH_SYSTEM = """
You are NeuroScout's final editor. Rewrite only for clarity and flow.

Return ONLY valid JSON with the same keys you received.

Rules:
- Keep all factual meaning and citations intact.
- Remove robotic phrasing.
- Tighten repetition.
- Improve readability without becoming casual or vague.
- Simplify overly technical language: prefer "because" over "due to the fact that", "fear" over "apprehension".
- If a technical term is used, ensure it is followed by a brief plain-language clarification.
- The critical_insight must read as ONE clear, mechanism-focused sentence. No poetic language or vague metaphors.
"""

REPAIR_SYSTEM = """
You are NeuroScout's repair engine. You receive a draft report, validation failures, and the source evidence.

Return ONLY valid JSON with the exact same schema as the report you received.

Rules:
- Repair only the failed dimensions.
- Preserve all valid parts of the draft when possible.
- Do not invent sources or citations.
- If asked to add a causal chain, include a MULTI-STEP chain (minimum 3 intermediate steps) using "->" or "leads to": A -> B -> C -> D -> Outcome. Single-step chains are NOT sufficient.
- The critical_insight MUST be ONE mechanism-focused sentence a non-expert can understand. No poetic language, no vague metaphors. Must be cross-domain, non-obvious, and not repeated from prior sections.
- If has_required_sections failed: ensure sections include "Neurological Mechanisms", "Psychological Mechanisms", "Behavioral Reinforcement Mechanisms", and "Cross-Domain Mechanism Chain".
- If has_behavioral_economics failed: add at least TWO different biases from: loss aversion, sunk cost fallacy, confirmation bias, framing effect, self-handicapping, present bias, temporal discounting, anchoring, status quo bias. Include relatable, well-known biases people recognize.
- If has_human_reality_layer failed: add social validation, FOMO, social comparison, or emotional regulation loops. Include concrete patterns: procrastination before deadlines, quitting near success, avoiding high-stakes opportunities.
- If has_mechanism_depth failed: ensure each section explains WHY (cause), HOW (process), and WHAT (effect).
- If has_real_world_examples failed: add concrete examples using "for example", "consider when", "in everyday life". Reader should think "that is exactly what I do".
- If has_identity_loop failed: add an explicit identity feedback loop: identity -> behavior -> outcome -> identity reinforcement. Show how self-concept drives behavior that confirms itself.
- If has_escalation_pattern failed: show escalation from small avoidance -> repeated delay -> major self-sabotage. Include short-term relief -> behavior repetition -> habit formation.
- For evidence_gaps: each gap must be an object with 'gap', 'reason', and 'needed' keys.
- If has_strong_sources failed: ensure at least 2 research/clinical/official sources AND no more than 50% general/blog sources.
- Use clear, simple language. Maintain depth but eliminate unnecessary jargon.
"""

HIGH_AUTHORITY_SOURCE_TYPES = {"research", "clinical", "official"}
DECISION_KEYWORDS = {
    "decision",
    "motivation",
    "delay",
    "avoidance",
    "reward",
    "self-control",
    "procrastination",
    "habit",
    "dopamine",
    "addiction",
    "sabotage",
    "self-sabotage",
    "failure",
    "success",
    "impulse",
}
BEHAVIORAL_ECON_TERMS = {
    "present bias",
    "hyperbolic discounting",
    "temporal discounting",
    "reward prediction error",
    "habit loop",
    "loss aversion",
    "sunk cost",
    "confirmation bias",
    "framing effect",
    "anchoring bias",
    "status quo bias",
    "endowment effect",
    "availability heuristic",
    "bounded rationality",
    "prospect theory",
    "self-handicapping",
    "learned helplessness",
    "approach-avoidance",
}
CAUSAL_CHAIN_MARKERS = ("->", "→", "leads to", "results in", "causes")
MECHANISM_MARKERS = ("because", "driven by", "through", "mechanism", "process", "which causes", "which leads to")
HUMAN_REALITY_TERMS = {
    "social validation",
    "fomo",
    "fear of missing out",
    "social comparison",
    "emotional regulation",
    "peer influence",
    "peer pressure",
    "social proof",
}
REQUIRED_SECTION_KEYWORDS = {
    "neurological": {"neurological", "neural", "brain", "neuroscience"},
    "psychological": {"psychological", "cognitive", "psychology"},
    "behavioral_reinforcement": {"behavioral reinforcement", "reinforcement mechanism", "habit loop", "reward dynamics", "conditioning"},
    "cross_domain": {"cross-domain", "cross domain", "mechanism chain", "interdisciplinary"},
}
DOMAIN_KEYWORDS = {
    "neuroscience": {"brain", "neural", "amygdala", "prefrontal", "dopamine", "cortisol", "serotonin", "hippocampus"},
    "psychology": {"cognitive", "emotion", "anxiety", "rumination", "avoidance", "psychology", "attachment", "schema"},
    "economics": {"bias", "discounting", "reward", "incentive", "economics", "present bias", "utility", "cost-benefit"},
    "behavior": {"habit", "routine", "behavior", "loop", "reinforcement", "conditioning", "operant", "stimulus"},
    "sociology": {"social", "peer", "group", "norm", "conformity", "culture", "identity"},
}


async def run_research(
    query: str,
    max_iterations: int = MAX_ITERATIONS_DEFAULT,
    mode: str = "balanced",
    observer: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    if not GEMINI_API_KEY:
        yield {"type": "error", "ts": _now_iso(), "message": "GEMINI_API_KEY not configured"}
        return

    started = time.time()
    session_id = f"neuroscout-{uuid.uuid4()}"
    max_iterations = max(2, min(8, max_iterations))
    mode = mode if mode in {"quick", "balanced", "deep"} else "balanced"

    yield {
        "type": "start",
        "ts": _now_iso(),
        "query": query,
        "mode": mode,
        "max_iterations": max_iterations,
    }
    _emit(observer, "run_started", mode=mode, query_length=len(query))

    yield {
        "type": "plan",
        "ts": _now_iso(),
        "status": "running",
        "message": "Building a structured research plan",
    }
    try:
        llm_started = time.time()
        planner = _new_chat(PLAN_SYSTEM)
        plan_resp = await planner.send_message(
            json.dumps(
                {
                    "query": query,
                    "mode": mode,
                    "required_intents": ["definition", "mechanism", "comparison", "debate", "edge_case"],
                }
            )
        )
        plan_raw = _safe_json(plan_resp)
        _emit(observer, "llm_call", stage="plan", duration_ms=round((time.time() - llm_started) * 1000, 2))
    except Exception as exc:
        yield {"type": "error", "ts": _now_iso(), "message": f"Planner failed: {exc}"}
        return

    plan_items = []
    if isinstance(plan_raw, list):
        for item in plan_raw:
            if not isinstance(item, dict):
                continue
            sub_question = str(item.get("sub_question") or "").strip()
            intent = str(item.get("intent") or "").strip().lower()
            search_queries = [
                str(q).strip()
                for q in item.get("search_queries", [])
                if str(q).strip()
            ][:2]
            if sub_question and search_queries:
                plan_items.append(
                    {
                        "sub_question": sub_question,
                        "intent": intent or "comparison",
                        "search_queries": search_queries,
                    }
                )
    if not plan_items:
        plan_items = _default_plan(query)
    plan_items = plan_items[:MAX_SUBQUESTIONS]

    yield {
        "type": "plan",
        "ts": _now_iso(),
        "status": "done",
        "message": f"Planned {len(plan_items)} research angles",
        "plan": plan_items,
        "sub_questions": [item["sub_question"] for item in plan_items],
    }
    _emit(observer, "plan_completed", plan_items=len(plan_items))

    keyword_pool = _keyword_pool(query, plan_items)
    sources: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_domains_per_iteration: set[str] = set()
    queued_queries: List[Dict[str, Any]] = []

    for item in plan_items:
        for search_query in item["search_queries"]:
            queued_queries.append(
                {
                    "query": search_query,
                    "sub_question": item["sub_question"],
                    "intent": item["intent"],
                    "reason": "planner",
                }
            )

    critique_state = {
        "missing_aspects": [],
        "weak_points": [],
        "conflicts": [],
        "confidence_summary": "medium",
    }

    async with httpx.AsyncClient() as http_client:
        iterations_used = 0
        while queued_queries and iterations_used < max_iterations:
            job = queued_queries.pop(0)
            iterations_used += 1
            seen_domains_per_iteration.clear()

            yield {
                "type": "search",
                "ts": _now_iso(),
                "status": "running",
                "iteration": iterations_used,
                "query": job["query"],
                "intent": job["intent"],
                "message": f"Searching for {job['intent']} evidence",
            }

            search_started = time.time()
            cached_results = _cache_get(SEARCH_CACHE, job["query"], SEARCH_CACHE_TTL_SEC)
            search_cache_hit = cached_results is not None
            if cached_results is None:
                raw_results = await asyncio.to_thread(_ddg_search, job["query"], MAX_RESULTS_PER_QUERY)
                _cache_set(SEARCH_CACHE, job["query"], raw_results)
            else:
                raw_results = cached_results
            _emit(
                observer,
                "search_completed",
                cache_hit=search_cache_hit,
                duration_ms=round((time.time() - search_started) * 1000, 2),
                result_count=len(raw_results),
            )
            ranked_results = []
            for result in raw_results:
                source_type = _detect_source_type(result["url"], result["title"], result["snippet"])
                score = _score_result({**result, "source_type": source_type}, keyword_pool)
                ranked_results.append({**result, "source_type": source_type, "source_quality_score": score})

            ranked_results.sort(key=lambda item: item["source_quality_score"], reverse=True)
            selected_results = []
            for result in ranked_results:
                normalized_url = _normalize_url(result["url"])
                domain = _domain(result["url"])
                if normalized_url in seen_urls or domain in seen_domains_per_iteration:
                    continue
                seen_domains_per_iteration.add(domain)
                seen_urls.add(normalized_url)
                selected_results.append(result)
                if len(selected_results) >= (2 if mode == "quick" else 3):
                    break

            yield {
                "type": "search",
                "ts": _now_iso(),
                "status": "done",
                "iteration": iterations_used,
                "query": job["query"],
                "results_count": len(selected_results),
                "results": [
                    {
                        "title": r["title"],
                        "url": r["url"],
                        "source_type": r["source_type"],
                        "source_quality_score": r["source_quality_score"],
                    }
                    for r in selected_results
                ],
            }

            if selected_results:
                yield {
                    "type": "observe",
                    "ts": _now_iso(),
                    "status": "running",
                    "message": f"Extracting evidence from {len(selected_results)} sources",
                }
                fetched_pages = await asyncio.gather(*[_fetch_page(r["url"], http_client) for r in selected_results])
                _emit(
                    observer,
                    "fetch_completed",
                    fetched_count=len(fetched_pages),
                    cache_hits=sum(1 for page in fetched_pages if page.get("_cache_hit")),
                )
                added_sources = 0
                for result, page in zip(selected_results, fetched_pages):
                    evidence_units = _extract_evidence_units(
                        page,
                        keyword_pool,
                        job["sub_question"],
                        result["source_type"],
                        result["source_quality_score"],
                    )
                    if not evidence_units:
                        continue
                    sources.append(
                        {
                            "url": result["url"],
                            "title": page.get("title") or result["title"] or result["url"],
                            "snippet": result["snippet"],
                            "sub_question": job["sub_question"],
                            "intent": job["intent"],
                            "source_type": result["source_type"],
                            "source_quality_score": result["source_quality_score"],
                            "accessed_date": _now_iso(),
                            "evidence_units": evidence_units,
                        }
                    )
                    added_sources += 1
                sources = sorted(
                    sources,
                    key=lambda item: (
                        item.get("source_quality_score", 0),
                        max((u.get("confidence_score", 0) for u in item.get("evidence_units", [])), default=0),
                    ),
                    reverse=True,
                )[:MAX_EVIDENCE_UNITS]
                yield {
                    "type": "observe",
                    "ts": _now_iso(),
                    "status": "done",
                    "message": f"Captured {added_sources} high-value sources",
                    "total_sources": len(sources),
                }
                _emit(observer, "sources_updated", total_sources=len(sources), added_sources=added_sources)

            yield {
                "type": "reason",
                "ts": _now_iso(),
                "status": "running",
                "message": "Critiquing evidence quality and coverage",
            }
            evidence_summary = _summarize_evidence_units(sources)
            reason_prompt = json.dumps(
                {
                    "query": query,
                    "mode": mode,
                    "plan": plan_items,
                    "current_iteration": iterations_used,
                    "evidence_summary": evidence_summary[:10000],
                }
            )
            try:
                llm_started = time.time()
                critic = _new_chat(REASON_SYSTEM)
                reason_resp = await critic.send_message(reason_prompt)
                decision = _safe_json(reason_resp) or {}
                _emit(observer, "llm_call", stage="reason", duration_ms=round((time.time() - llm_started) * 1000, 2))
            except Exception:
                decision = {}

            sufficient = bool(decision.get("sufficient", len(sources) >= 4))
            critique_state = {
                "missing_aspects": [str(x) for x in decision.get("missing_aspects", []) if str(x).strip()][:4],
                "weak_points": [str(x) for x in decision.get("weak_points", []) if str(x).strip()][:4],
                "conflicts": [
                    {
                        "topic": str(x.get("topic") or "").strip(),
                        "source_a": int(x.get("source_a") or 0),
                        "source_b": int(x.get("source_b") or 0),
                        "summary": str(x.get("summary") or "").strip(),
                    }
                    for x in decision.get("conflicts", [])
                    if isinstance(x, dict)
                ][:4],
                "confidence_summary": str(decision.get("confidence_summary") or "medium").lower(),
            }
            new_queries = [
                str(q).strip()
                for q in decision.get("new_queries", [])
                if str(q).strip()
            ][:2]
            for refined in new_queries:
                if all(existing["query"] != refined for existing in queued_queries):
                    queued_queries.append(
                        {
                            "query": refined,
                            "sub_question": critique_state["missing_aspects"][0] if critique_state["missing_aspects"] else "follow-up",
                            "intent": "debate" if critique_state["conflicts"] else "comparison",
                            "reason": "critic",
                        }
                    )

            yield {
                "type": "reason",
                "ts": _now_iso(),
                "status": "done",
                "sufficient": sufficient,
                "missing_aspects": critique_state["missing_aspects"],
                "weak_points": critique_state["weak_points"],
                "conflicts": critique_state["conflicts"],
                "new_queries": new_queries,
                "confidence_summary": critique_state["confidence_summary"],
                "message": "Evidence appears sufficient" if sufficient else "Critic requested targeted follow-up searches",
            }
            _emit(
                observer,
                "reason_completed",
                sufficient=sufficient,
                missing_count=len(critique_state["missing_aspects"]),
                conflict_count=len(critique_state["conflicts"]),
                new_query_count=len(new_queries),
            )

            if sufficient and (mode != "deep" or len(sources) >= 5):
                break

    if not sources:
        yield {
            "type": "error",
            "ts": _now_iso(),
            "message": "No usable evidence retrieved from web search.",
        }
        return

    if _count_high_authority_sources(sources) < 2:
        yield {
            "type": "reason",
            "ts": _now_iso(),
            "status": "running",
            "message": "High-authority source minimum not met, searching for stronger evidence",
        }
        async with httpx.AsyncClient() as http_client:
            sources = await _search_for_high_authority_sources(
                query,
                keyword_pool,
                sources,
                seen_urls,
                http_client,
                observer=observer,
            )
        yield {
            "type": "reason",
            "ts": _now_iso(),
            "status": "done",
            "message": f"High-authority sources after repair search: {_count_high_authority_sources(sources)}",
        }

    yield {
        "type": "synthesize",
        "ts": _now_iso(),
        "status": "running",
        "message": f"Synthesizing report from {len(sources)} curated sources",
    }
    evidence_payload = []
    for idx, source in enumerate(sources, start=1):
        evidence_payload.append(
            {
                "source_id": idx,
                "title": source["title"],
                "url": source["url"],
                "source_type": source["source_type"],
                "source_quality_score": source["source_quality_score"],
                "sub_question": source["sub_question"],
                "intent": source["intent"],
                "evidence_units": source["evidence_units"][:2],
            }
        )

    synth_prompt = json.dumps(
        {
            "query": query,
            "mode": mode,
            "plan": plan_items,
            "top_source_ids": _top_references(sources),
            "critic": critique_state,
            "evidence": evidence_payload,
        }
    )
    try:
        llm_started = time.time()
        synthesizer = _new_chat(SYNTHESIZE_SYSTEM)
        synth_resp = await synthesizer.send_message(synth_prompt)
        parsed = _safe_json(synth_resp)
        _emit(observer, "llm_call", stage="synthesize", duration_ms=round((time.time() - llm_started) * 1000, 2))
    except Exception as exc:
        yield {"type": "error", "ts": _now_iso(), "message": f"Synthesis failed: {exc}"}
        return

    if not isinstance(parsed, dict) or "sections" not in parsed:
        yield {"type": "error", "ts": _now_iso(), "message": "Failed to parse synthesized report"}
        return

    try:
        llm_started = time.time()
        polisher = _new_chat(POLISH_SYSTEM)
        polish_resp = await polisher.send_message(json.dumps(parsed))
        polished = _safe_json(polish_resp)
        if isinstance(polished, dict) and polished.get("sections"):
            parsed = polished
        _emit(observer, "llm_call", stage="polish", duration_ms=round((time.time() - llm_started) * 1000, 2))
    except Exception:
        pass

    references = [
        {
            "id": idx,
            "title": source["title"],
            "url": source["url"],
            "accessed_date": source["accessed_date"],
            "source_type": source["source_type"],
            "source_quality_score": source["source_quality_score"],
        }
        for idx, source in enumerate(sources, start=1)
    ]

    validation = validate_output(parsed, references, query)
    yield {
        "type": "reason",
        "ts": _now_iso(),
        "status": "running",
        "message": "Validating synthesized report against quality gates",
    }
    _emit(observer, "validation_completed", passed=sum(1 for passed in validation.values() if passed), failed=sum(1 for passed in validation.values() if not passed))

    failed_checks = [name for name, passed in validation.items() if not passed]
    if failed_checks:
        yield {
            "type": "reason",
            "ts": _now_iso(),
            "status": "done",
            "message": f"Validation failed on: {', '.join(failed_checks)}. Running targeted repair.",
            "validation": validation,
        }
        repair_prompt = json.dumps(
            {
                "query": query,
                "mode": mode,
                "failed_checks": failed_checks,
                "rules": {
                    "causal_chain": "Include a MULTI-STEP causal chain (3+ intermediate steps) using A -> B -> C -> D -> Outcome. Single-step chains are NOT sufficient.",
                    "strong_sources": "Require 2+ research/clinical/official sources AND no more than 50% general/blog sources.",
                    "insight_quality": "ONE mechanism-focused sentence a non-expert can understand. No poetic language or metaphors. Must explain WHY, be cross-domain, non-obvious, and generalizable.",
                    "mechanism_depth": "Sections must explain WHY (cause), HOW (process), and WHAT outcome follows.",
                    "behavioral_economics": "Include at least TWO DIFFERENT biases: loss aversion, sunk cost, confirmation bias, framing effect, self-handicapping, present bias, temporal discounting. Prefer relatable biases. For self-control/avoidance topics, MUST include temporal discounting or present bias.",
                    "human_reality_layer": "Include real-world drivers: social validation, FOMO, social comparison, emotional regulation. Include concrete patterns: procrastination before deadlines, quitting near success, avoiding high-stakes opportunities.",
                    "required_sections": "Sections MUST include: Neurological Mechanisms, Psychological Mechanisms, Behavioral Reinforcement Mechanisms, and Cross-Domain Mechanism Chain.",
                    "evidence_gap_depth": "Each evidence gap must be an object with 'gap', 'reason', and 'needed' keys.",
                    "real_world_examples": "Include concrete real-world examples using 'for example', 'consider when', 'in everyday life'. Reader should think 'that is exactly what I do'.",
                    "identity_loop": "Model identity -> behavior -> outcome -> identity reinforcement. Show how self-concept drives behavior that confirms itself in a self-perpetuating cycle.",
                    "escalation_pattern": "Show escalation: small avoidance -> repeated delay -> major self-sabotage. Include short-term relief -> behavior repetition -> habit formation.",
                },
                "draft_report": parsed,
                "evidence": evidence_payload,
            }
        )
        try:
            llm_started = time.time()
            repairer = _new_chat(REPAIR_SYSTEM)
            repair_resp = await repairer.send_message(repair_prompt)
            repaired = _safe_json(repair_resp)
            _emit(observer, "llm_call", stage="repair", duration_ms=round((time.time() - llm_started) * 1000, 2))
            if isinstance(repaired, dict) and repaired.get("sections"):
                repaired_validation = validate_output(repaired, references, query)
                if sum(1 for passed in repaired_validation.values() if passed) >= sum(1 for passed in validation.values() if passed):
                    parsed = repaired
                    validation = repaired_validation
        except Exception:
            pass
    else:
        yield {
            "type": "reason",
            "ts": _now_iso(),
            "status": "done",
            "message": "Validation passed",
            "validation": validation,
        }

    duration = round(time.time() - started, 2)
    telemetry = {
        "search_cache_entries": len(SEARCH_CACHE),
        "fetch_cache_entries": len(FETCH_CACHE),
        "source_count": len(sources),
        "top_source_count": len(_top_references(sources)),
    }
    report = {
        "report_id": str(uuid.uuid4()),
        "query": query,
        "mode": mode,
        "executive_summary": parsed.get("executive_summary", ""),
        "sections": parsed.get("sections", []),
        "critical_insight": parsed.get("critical_insight", ""),
        "common_misconceptions": parsed.get("common_misconceptions", []),
        "conflicting_evidence": parsed.get("conflicting_evidence", critique_state["conflicts"]),
        "evidence_gaps": parsed.get("evidence_gaps", critique_state["missing_aspects"]),
        "confidence_summary": parsed.get(
            "confidence_summary",
            {
                "overall": critique_state["confidence_summary"],
                "rationale": "Confidence inferred from source quality, evidence depth, and remaining gaps.",
            },
        ),
        "key_takeaways": parsed.get("key_takeaways", []),
        "references": references,
        "top_source_ids": _top_references(sources),
        "plan": plan_items,
        "search_iterations": iterations_used,
        "generation_time_sec": duration,
        "created_at": _now_iso(),
        "telemetry": {**telemetry, "validation": validation},
    }

    yield {
        "type": "synthesize",
        "ts": _now_iso(),
        "status": "done",
        "message": f"Report ready in {duration}s",
    }
    _emit(
        observer,
        "run_completed",
        duration_sec=duration,
        search_iterations=iterations_used,
        source_count=len(sources),
    )
    yield {"type": "final", "ts": _now_iso(), "report": report}


def _ddg_search(query: str, max_results: int) -> List[Dict[str, str]]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="wt-wt"))
        normalized = []
        for result in results:
            normalized.append(
                {
                    "title": result.get("title") or result.get("heading") or "",
                    "url": result.get("href") or result.get("url") or result.get("link") or "",
                    "snippet": result.get("body") or result.get("snippet") or "",
                }
            )
        return [item for item in normalized if item["url"]]
    except Exception:
        return []


def get_cache_stats() -> Dict[str, Any]:
    return {
        "search_cache_entries": len(SEARCH_CACHE),
        "fetch_cache_entries": len(FETCH_CACHE),
        "search_cache_ttl_sec": SEARCH_CACHE_TTL_SEC,
        "fetch_cache_ttl_sec": FETCH_CACHE_TTL_SEC,
    }
