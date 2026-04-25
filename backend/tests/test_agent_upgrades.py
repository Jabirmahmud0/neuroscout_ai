from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import (
    _default_plan,
    _detect_source_type,
    _extract_evidence_units,
    _score_result,
    _top_references,
    check_causal_chain,
    check_insight_quality,
    get_cache_stats,
    validate_output,
)


def test_default_plan_has_structured_queries():
    plan = _default_plan("overthinking")
    assert len(plan) >= 3
    assert all(item["intent"] for item in plan)
    assert all(len(item["search_queries"]) >= 2 for item in plan)


def test_source_type_prefers_research_and_official_domains():
    assert _detect_source_type(
        "https://pubmed.ncbi.nlm.nih.gov/123/",
        "Study on rumination",
        "systematic review of anxiety disorders",
    ) == "research"
    assert _detect_source_type(
        "https://www.cdc.gov/mentalhealth/index.html",
        "Mental health",
        "official guidance",
    ) == "official"


def test_extract_evidence_units_filters_for_relevant_paragraphs():
    page = {
        "content": "\n".join(
            [
                "Short line",
                "Rumination is a repetitive negative thinking pattern that appears in anxiety and depression research.",
                "Another paragraph about driving fear and avoidance behaviour in clinical settings.",
                "Unrelated content about gardening and soil conditions that should score poorly.",
            ]
        )
    }
    units = _extract_evidence_units(
        page,
        ["rumination", "driving", "anxiety"],
        "What mechanisms explain rumination?",
        "research",
        0.9,
    )
    assert units
    assert all(unit["relevance_score"] >= 0.25 for unit in units)
    assert "rumination" in units[0]["excerpt"].lower() or "driving" in units[0]["excerpt"].lower()


def test_score_result_rewards_relevant_high_quality_sources():
    research_score = _score_result(
        {
            "title": "Systematic review of rumination and anxiety",
            "snippet": "Clinical review and mechanisms",
            "source_type": "research",
        },
        ["rumination", "anxiety", "mechanism"],
    )
    blog_score = _score_result(
        {
            "title": "My thoughts on overthinking",
            "snippet": "personal blog post",
            "source_type": "blog",
        },
        ["rumination", "anxiety", "mechanism"],
    )
    assert research_score > blog_score


def test_top_references_returns_best_ranked_source_ids():
    ids = _top_references(
        [
            {
                "source_quality_score": 0.5,
                "evidence_units": [{"confidence_score": 0.5}],
            },
            {
                "source_quality_score": 0.9,
                "evidence_units": [{"confidence_score": 0.8}],
            },
            {
                "source_quality_score": 0.85,
                "evidence_units": [{"confidence_score": 0.9}],
            },
        ]
    )
    assert ids[0] in {2, 3}
    assert len(ids) == 3


def test_cache_stats_exposes_expected_keys():
    stats = get_cache_stats()
    assert "search_cache_entries" in stats
    assert "fetch_cache_entries" in stats
    assert "search_cache_ttl_sec" in stats
    assert "fetch_cache_ttl_sec" in stats


def test_validation_gate_detects_causal_chain_and_strong_sources():
    report = {
        "executive_summary": "Summary [1]",
        "sections": [
            {
                "heading": "Mechanism",
                "content": "Present bias leads to short-term reward seeking, which causes delay and results in procrastination [1,2].",
            }
        ],
        "critical_insight": "The counterintuitive point is that procrastination is not just laziness; it is a cross-domain reward calibration problem spanning psychology and economics [1,2].",
    }
    references = [
        {"id": 1, "source_type": "research"},
        {"id": 2, "source_type": "clinical"},
    ]
    results = validate_output(report, references, "why do people procrastinate")
    assert results["has_causal_chain"] is True
    assert results["has_strong_sources"] is True
    assert results["has_behavioral_economics"] is True


def test_insight_quality_rejects_generic_claim():
    assert check_insight_quality({"critical_insight": "People avoid discomfort.", "sections": []}) is False
    assert check_causal_chain(
        {
            "sections": [{"content": "Stress leads to avoidance and causes missed deadlines."}],
            "critical_insight": "",
        }
    ) is True
