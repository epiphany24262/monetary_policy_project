from pathlib import Path

import pandas as pd

from src.monetary_policy.sample import verify_final_analysis_plan


def test_final_analysis_plan_is_locked_and_verified():
    verify_final_analysis_plan()
    assert any(Path(rel).exists() for rel in ["research/final_analysis_plan.md", "configs/final_analysis_plan.md"])
    assert any(Path(rel).exists() for rel in ["research/final_analysis_plan.sha256", "configs/final_analysis_plan.sha256"])


def test_text_features_keep_2026q1_out_of_formal_sample():
    features = pd.read_csv("data/processed/text_features.csv")
    assert len(features) == 81
    assert features["in_formal_sample"].sum() == 80
    row = features.loc[features["report_period"] == "2026Q1"].iloc[0]
    assert not bool(row["in_formal_sample"])
    assert features.loc[features["in_formal_sample"], "guidance_novelty"].notna().sum() == 79


def test_manual_annotation_file_is_balanced_and_unlabeled():
    path = Path("data/validation/manual_sentence_annotation.xlsx")
    assert path.exists()
    sample = pd.read_excel(path)
    assert len(sample) == 240
    assert set(sample["section"]) == {"guidance", "macro"}
    counts = sample["section"].value_counts()
    assert abs(counts["guidance"] - counts["macro"]) <= 2
    for col in ["manual_sentiment_label", "manual_policy_stance_label", "manual_topic_label"]:
        assert sample[col].fillna("").eq("").all()
