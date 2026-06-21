from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.monetary_policy.analysis.regressions import ols_hc3, total_effect
from src.monetary_policy.paths import ROOT
from src.monetary_policy.text.sentiment import expanding_unexpected


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def load_annotations() -> pd.DataFrame:
    path = ROOT / "data/validation/manual_sentence_annotation_filled.xlsx"
    df = pd.read_excel(path)
    # The workbook is the frozen, manually reviewed annotation source.
    df["text"] = df["sentence"].map(normalize_text)
    return df


def policy_model() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(2, 4),
                    min_df=1,
                    max_features=8000,
                    sublinear_tf=True,
                ),
            ),
            ("classifier", LinearSVC(class_weight="balanced", C=1.0)),
        ]
    )


def crossfit_policy(seed: int) -> tuple[pd.DataFrame, dict]:
    annotations = load_annotations()
    labeled = annotations[annotations["section"] == "guidance"].copy().reset_index(drop=True)
    all_sentences = pd.read_csv(ROOT / "data/processed/report_sentences.csv")
    all_sentences = all_sentences[all_sentences["section"] == "guidance"].copy()
    all_sentences["text"] = all_sentences["sentence"].map(normalize_text)
    all_sentences = all_sentences[all_sentences["text"].str.len().between(12, 300)].copy()

    X = labeled["text"].to_numpy()
    y = labeled["manual_policy_stance_label"].to_numpy()
    groups = labeled["report_id"].to_numpy()
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)

    oof_pred = np.empty(len(labeled), dtype=object)
    sentence_predictions: list[pd.DataFrame] = []
    fold_manifest: list[dict] = []

    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y, groups), start=1):
        train_reports = sorted(set(groups[train_idx]))
        test_reports = sorted(set(groups[test_idx]))
        model = clone(policy_model())
        model.fit(X[train_idx], y[train_idx])
        oof_pred[test_idx] = model.predict(X[test_idx])

        target = all_sentences[all_sentences["report_id"].isin(test_reports)].copy()
        target["predicted_policy"] = model.predict(target["text"].to_numpy())
        target["fold"] = fold
        sentence_predictions.append(target)
        fold_manifest.append(
            {
                "fold": fold,
                "train_reports": len(train_reports),
                "test_reports": len(test_reports),
                "test_report_ids": test_reports,
            }
        )

    cv_metrics = {
        "seed": seed,
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, oof_pred)),
        "macro_f1": float(f1_score(y, oof_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y, oof_pred, average="weighted", zero_division=0)),
        "hawkish_recall": float(
            ((oof_pred == "hawkish") & (y == "hawkish")).sum() / max((y == "hawkish").sum(), 1)
        ),
        "dovish_recall": float(
            ((oof_pred == "dovish") & (y == "dovish")).sum() / max((y == "dovish").sum(), 1)
        ),
        "fold_manifest": fold_manifest,
    }

    pred = pd.concat(sentence_predictions, ignore_index=True)
    counts = (
        pred.groupby(["report_id", "predicted_policy"]).size().unstack(fill_value=0).reset_index()
    )
    for label in ["dovish", "hawkish", "neutral", "irrelevant"]:
        if label not in counts.columns:
            counts[label] = 0
    counts["total"] = counts[["dovish", "hawkish", "neutral", "irrelevant"]].sum(axis=1)
    counts["relevant_total"] = counts[["dovish", "hawkish", "neutral"]].sum(axis=1)
    counts["directional_total"] = counts[["dovish", "hawkish"]].sum(axis=1)
    counts["stance_net_all"] = (counts["dovish"] - counts["hawkish"]) / counts["total"].clip(lower=1)
    counts["stance_net_relevant"] = (counts["dovish"] - counts["hawkish"]) / counts[
        "relevant_total"
    ].clip(lower=1)
    counts["stance_net_directional"] = (counts["dovish"] - counts["hawkish"]) / counts[
        "directional_total"
    ].clip(lower=1)
    counts["policy_relevance_share"] = counts["relevant_total"] / counts["total"].clip(lower=1)
    counts["seed"] = seed
    return counts, cv_metrics


def add_unexpected(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    out = panel.sort_values("report_period").copy()
    std = out[column].std(ddof=0)
    out[f"{column}_z"] = (out[column] - out[column].mean()) / (std if std else 1.0)
    unexpected = expanding_unexpected(out[f"{column}_z"], min_history=6)
    out[f"{column}_unexpected"] = unexpected["unexpected_tone"].to_numpy()
    out[f"{column}_unexpected_x_post_2019"] = out[f"{column}_unexpected"] * out["post_2019"]
    return out


def run_market_probe(counts: pd.DataFrame, seed: int) -> list[dict]:
    bond = pd.read_csv(ROOT / "data/processed/refactor_yield_curve_event_panel.csv")
    merged = bond.merge(counts, left_on="report_period", right_on="report_id", how="inner")
    rows: list[dict] = []
    for definition in ["stance_net_all", "stance_net_relevant", "stance_net_directional"]:
        data = add_unexpected(merged, definition)
        tone = f"{definition}_unexpected"
        interaction = f"{definition}_unexpected_x_post_2019"
        x_cols = [tone, "action_nearby_core", "post_2019", interaction]
        for dependent in ["delta_slope_bp_0_3", "delta_level_bp_0_3", "delta_curvature_bp_0_3"]:
            result = ols_hc3(data, dependent, x_cols)
            total = total_effect(result, tone, interaction)
            rows.append(
                {
                    "seed": seed,
                    "definition": definition,
                    "dependent": dependent,
                    "n": result["n"],
                    "base_beta": result["params"].get(tone),
                    "base_p": result["pvalues"].get(tone),
                    "interaction_beta": result["params"].get(interaction),
                    "interaction_p": result["pvalues"].get(interaction),
                    "post_2019_total_beta": total["estimate"],
                    "post_2019_total_p": total["p_value"],
                    "r2": result["r2"],
                    "condition_number": result["condition_number"],
                }
            )
    return rows


def main() -> None:
    out_dir = ROOT / "output/experiments/text_pipeline_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_counts: list[pd.DataFrame] = []
    cv_rows: list[dict] = []
    market_rows: list[dict] = []
    for seed in range(5):
        counts, cv_metrics = crossfit_policy(seed)
        all_counts.append(counts)
        cv_rows.append({k: v for k, v in cv_metrics.items() if k != "fold_manifest"})
        market_rows.extend(run_market_probe(counts, seed))
        (out_dir / f"crossfit_fold_manifest_seed_{seed}.json").write_text(
            json.dumps(cv_metrics["fold_manifest"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    counts_df = pd.concat(all_counts, ignore_index=True)
    cv_df = pd.DataFrame(cv_rows)
    market_df = pd.DataFrame(market_rows)
    counts_df.to_csv(out_dir / "crossfit_report_policy_scores.csv", index=False, encoding="utf-8-sig")
    cv_df.to_csv(out_dir / "crossfit_policy_cv_metrics.csv", index=False, encoding="utf-8-sig")
    market_df.to_csv(out_dir / "crossfit_policy_market_results.csv", index=False, encoding="utf-8-sig")

    market_summary = (
        market_df.groupby(["definition", "dependent"])
        .agg(
            base_beta_mean=("base_beta", "mean"),
            base_beta_std=("base_beta", "std"),
            base_p_median=("base_p", "median"),
            base_p_min=("base_p", "min"),
            interaction_beta_mean=("interaction_beta", "mean"),
            interaction_beta_std=("interaction_beta", "std"),
            interaction_p_median=("interaction_p", "median"),
            post_total_beta_mean=("post_2019_total_beta", "mean"),
            post_total_beta_std=("post_2019_total_beta", "std"),
            post_total_p_median=("post_2019_total_p", "median"),
            r2_mean=("r2", "mean"),
        )
        .reset_index()
    )
    market_summary.to_csv(out_dir / "crossfit_policy_market_summary.csv", index=False, encoding="utf-8-sig")

    print("CV metrics across seeds")
    print(cv_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nMarket summary")
    print(market_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
