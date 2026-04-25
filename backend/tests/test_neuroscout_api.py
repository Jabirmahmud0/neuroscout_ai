"""NeuroScout AI - End-to-end backend tests.

Covers:
- /api/health
- /api/research/stream (SSE) with valid/invalid inputs
- /api/sessions (list)
- /api/sessions/{id} (detail)
- DELETE /api/sessions/{id}
"""
from __future__ import annotations

import json
import os
import re
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000"
BASE_URL = BASE_URL.rstrip("/")

SSE_TIMEOUT = 240  # seconds (agent loop may take 30-90s; allow buffer)


# ---------- helpers ---------- #

def _parse_sse_stream(response, timeout: int = SSE_TIMEOUT):
    """Yield parsed JSON events from a text/event-stream response."""
    start = time.time()
    buf = ""
    for raw in response.iter_lines(decode_unicode=True):
        if time.time() - start > timeout:
            raise TimeoutError("SSE stream exceeded timeout")
        if raw is None:
            continue
        if raw == "":
            # event boundary
            if buf:
                for line in buf.splitlines():
                    if line.startswith("data:"):
                        payload = line[len("data:"):].strip()
                        if payload:
                            try:
                                yield json.loads(payload)
                            except json.JSONDecodeError:
                                pass
                buf = ""
            continue
        buf += raw + "\n"
    # flush trailing
    if buf:
        for line in buf.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload:
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        pass


def _run_stream(query: str, max_iterations: int = 3):
    """Run SSE stream end-to-end and collect events."""
    url = f"{BASE_URL}/api/research/stream"
    with requests.post(
        url,
        json={"query": query, "mode": "balanced", "max_iterations": max_iterations},
        stream=True,
        timeout=SSE_TIMEOUT,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200, f"stream returned {resp.status_code}: {resp.text[:500]}"
        events = list(_parse_sse_stream(resp))
    return events


# ---------- tests ---------- #

class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["llm_configured"] is True
        assert "metrics" in data
        assert "cache" in data
        assert "ts" in data

    def test_metrics(self):
        r = requests.get(f"{BASE_URL}/api/metrics", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "runs" in data
        assert "search" in data
        assert "fetch" in data
        assert "llm" in data
        assert "cache" in data


class TestValidation:
    def test_empty_query_returns_422(self):
        r = requests.post(
            f"{BASE_URL}/api/research/stream",
            json={"query": ""},
            timeout=15,
        )
        assert r.status_code == 422

    def test_too_short_query_returns_422(self):
        # min_length=3
        r = requests.post(
            f"{BASE_URL}/api/research/stream",
            json={"query": "ab"},
            timeout=15,
        )
        assert r.status_code == 422

    def test_query_over_500_chars_returns_422(self):
        r = requests.post(
            f"{BASE_URL}/api/research/stream",
            json={"query": "x" * 501},
            timeout=15,
        )
        assert r.status_code == 422

    def test_missing_query_returns_422(self):
        r = requests.post(
            f"{BASE_URL}/api/research/stream",
            json={},
            timeout=15,
        )
        assert r.status_code == 422


# Module-level cache so we don't re-run the long SSE stream for every test
_stream_cache: dict = {}


def _get_completed_stream():
    """Run the agent once and cache events for downstream tests.
    Retries once with an alternate query if no search results were retrieved.
    """
    if _stream_cache.get("events"):
        return _stream_cache

    queries = [
        "benefits of green tea",
        "history of the Eiffel Tower",
    ]
    last_events = []
    for q in queries:
        events = _run_stream(q, max_iterations=3)
        last_events = events
        # Success if we saw a 'final' event
        if any(e.get("type") == "final" for e in events):
            _stream_cache["events"] = events
            _stream_cache["query"] = q
            return _stream_cache

    # Both queries failed to produce a final report
    _stream_cache["events"] = last_events
    _stream_cache["query"] = queries[-1]
    return _stream_cache


class TestResearchStream:
    def test_stream_produces_expected_event_sequence(self):
        cache = _get_completed_stream()
        events = cache["events"]
        assert events, "No SSE events received"

        types_seen = [e.get("type") for e in events]
        print(f"Event types seen: {types_seen}")

        # session event must be first
        assert events[0].get("type") == "session"
        assert "session_id" in events[0]
        _stream_cache["session_id"] = events[0]["session_id"]

        # Required events
        assert "start" in types_seen, f"Missing 'start' event. Got: {types_seen}"
        assert "plan" in types_seen, f"Missing 'plan' event. Got: {types_seen}"
        assert "search" in types_seen, f"Missing 'search' event. Got: {types_seen}"
        assert "done" in types_seen, f"Missing 'done' event. Got: {types_seen}"

        # Final must be present; if not, this is a web-search infra issue -> fail with diag
        if "final" not in types_seen:
            err_events = [e for e in events if e.get("type") == "error"]
            pytest.fail(
                f"No 'final' event produced. Errors: {err_events}. Types: {types_seen}. "
                "Possible DuckDuckGo rate limiting or synthesis failure."
            )

        assert "synthesize" in types_seen
        # 'done' must be last
        assert events[-1].get("type") == "done"
        assert events[-1].get("status") == "completed"

    def test_final_report_shape(self):
        cache = _get_completed_stream()
        events = cache["events"]
        final = next((e for e in events if e.get("type") == "final"), None)
        if final is None:
            pytest.skip("No final report event produced (see previous test).")

        report = final.get("report")
        assert isinstance(report, dict)

        # Required top-level fields
        assert report["query"] == cache["query"]
        assert report.get("mode") == "balanced"
        assert isinstance(report.get("executive_summary"), str)
        assert len(report["executive_summary"]) > 0
        assert isinstance(report.get("sections"), list) and len(report["sections"]) >= 1
        assert isinstance(report.get("references"), list) and len(report["references"]) >= 1
        assert isinstance(report.get("telemetry"), dict)
        assert isinstance(report.get("search_iterations"), int) and report["search_iterations"] >= 1
        assert isinstance(report.get("generation_time_sec"), (int, float))
        assert isinstance(report.get("created_at"), str)

        # Sections structure
        for sec in report["sections"]:
            assert "heading" in sec and isinstance(sec["heading"], str)
            assert "content" in sec and isinstance(sec["content"], str)

        # References structure
        ref_ids = set()
        for ref in report["references"]:
            assert isinstance(ref.get("id"), int)
            assert isinstance(ref.get("title"), str)
            assert isinstance(ref.get("url"), str) and ref["url"].startswith("http")
            assert isinstance(ref.get("accessed_date"), str)
            ref_ids.add(ref["id"])

        # Inline citation validation: at least one section's content contains [n] where n is a valid ref id
        citation_pattern = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
        any_valid_citation = False
        for sec in report["sections"]:
            matches = citation_pattern.findall(sec["content"])
            for grp in matches:
                for num in grp.split(","):
                    try:
                        n = int(num.strip())
                    except ValueError:
                        continue
                    if n in ref_ids:
                        any_valid_citation = True
                        break
        assert any_valid_citation, (
            "No section contains a valid inline [n] citation pointing to a reference. "
            "Report is not properly grounded."
        )


class TestSessions:
    def test_list_sessions_contains_created(self):
        cache = _get_completed_stream()
        session_id = _stream_cache.get("session_id")
        if not session_id:
            pytest.skip("No session_id captured from stream")

        r = requests.get(f"{BASE_URL}/api/sessions", timeout=20)
        assert r.status_code == 200
        sessions = r.json()
        assert isinstance(sessions, list)
        ids = [s["session_id"] for s in sessions]
        assert session_id in ids, f"Created session {session_id} not in list {ids[:5]}..."

        # status should be completed if 'final' produced, else failed
        me = next(s for s in sessions if s["session_id"] == session_id)
        expected_final = any(e.get("type") == "final" for e in cache["events"])
        assert me["status"] == ("completed" if expected_final else "failed")
        assert me["query"] == cache["query"]

        # Sorted descending by created_at
        if len(sessions) >= 2:
            assert sessions[0]["created_at"] >= sessions[-1]["created_at"]

    def test_get_session_detail(self):
        session_id = _stream_cache.get("session_id")
        if not session_id:
            pytest.skip("No session_id captured from stream")
        r = requests.get(f"{BASE_URL}/api/sessions/{session_id}", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == session_id
        assert data["status"] in ("completed", "failed")
        if data["status"] == "completed":
            assert isinstance(data.get("report"), dict)
            assert "sections" in data["report"]
            assert "references" in data["report"]

    def test_get_session_detail_not_found(self):
        r = requests.get(f"{BASE_URL}/api/sessions/does-not-exist-xyz", timeout=15)
        assert r.status_code == 404

    def test_delete_session(self):
        session_id = _stream_cache.get("session_id")
        if not session_id:
            pytest.skip("No session_id captured from stream")
        r = requests.delete(f"{BASE_URL}/api/sessions/{session_id}", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body.get("deleted") is True

        # Subsequent GET -> 404
        r2 = requests.get(f"{BASE_URL}/api/sessions/{session_id}", timeout=15)
        assert r2.status_code == 404

    def test_delete_session_not_found(self):
        r = requests.delete(f"{BASE_URL}/api/sessions/nope-xyz-missing", timeout=15)
        assert r.status_code == 404
