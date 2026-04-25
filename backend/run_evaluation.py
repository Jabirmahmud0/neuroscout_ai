from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from agent import run_research

ROOT = Path(__file__).parent
DEFAULT_CASES = ROOT / "evaluation_cases.json"


async def _run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    events = []
    final_report = None
    async for event in run_research(
        case["query"],
        max_iterations=6 if case.get("mode") == "deep" else 4,
        mode=case.get("mode", "balanced"),
    ):
        events.append(event)
        if event.get("type") == "final":
            final_report = event.get("report")

    if final_report is None:
        return {
            "id": case["id"],
            "query": case["query"],
            "passed": False,
            "errors": ["no final report"],
            "event_types": [event.get("type") for event in events],
        }

    expect = case.get("expect", {})
    errors: List[str] = []
    sections = final_report.get("sections", [])
    references = final_report.get("references", [])
    headings = " ".join(section.get("heading", "") for section in sections).lower()

    if len(sections) < expect.get("min_sections", 1):
        errors.append(f"expected at least {expect.get('min_sections')} sections, got {len(sections)}")
    if len(references) < expect.get("min_references", 1):
        errors.append(f"expected at least {expect.get('min_references')} references, got {len(references)}")

    for needle in expect.get("must_include_headings", []):
        if needle.lower() not in headings:
            errors.append(f"missing heading/theme containing '{needle}'")

    if expect.get("require_conflicts_or_gaps"):
        if not final_report.get("conflicting_evidence") and not final_report.get("evidence_gaps"):
            errors.append("expected conflicting evidence or evidence gaps section")

    return {
        "id": case["id"],
        "query": case["query"],
        "mode": case.get("mode", "balanced"),
        "passed": not errors,
        "errors": errors,
        "summary": {
            "sections": len(sections),
            "references": len(references),
            "search_iterations": final_report.get("search_iterations"),
            "generation_time_sec": final_report.get("generation_time_sec"),
            "confidence": final_report.get("confidence_summary", {}).get("overall"),
        },
    }


async def _main(cases_path: Path) -> int:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        results.append(await _run_case(case))

    passed = sum(1 for result in results if result["passed"])
    payload = {
        "cases": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
    }
    print(json.dumps(payload, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NeuroScout benchmark cases.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES), help="Path to evaluation cases JSON file")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(Path(args.cases))))
