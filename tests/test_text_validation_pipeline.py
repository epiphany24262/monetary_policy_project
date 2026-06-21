from __future__ import annotations

from src.monetary_policy.text.validation_report import run_text_validation


def test_validation_rescores_current_lexicon_and_reports_direction_metric() -> None:
    result = run_text_validation()
    summary = result["summary"]

    assert summary["score_source"] == "current_lexicon_rescore"
    assert summary["lexicon_version"] >= 2
    assert summary["stored_stance_score_mismatch_count"] > 0
    assert "policy_direction" in result
    assert result["policy_direction"]["n"] > 0
    assert set(result["policy_direction"]["labels_used"]).issubset(
        {"dovish", "hawkish", "neutral"}
    )
