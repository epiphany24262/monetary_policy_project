"""Cross-fitted policy tone via grouped cross-validation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from ..paths import PROCESSED_DIR, OUTPUT_DIR
from ..text.supervised_classifier import build_vectorizer, build_classifier, make_report_duplicate_groups

SEEDS = [42, 2026, 3407]


def _decision_scores(clf, X):
    """Get decision scores for each class (one-vs-rest)."""
    classes = clf.classes_
    raw = clf.decision_function(X)
    if raw.ndim == 1:
        scores = np.column_stack([-raw, raw])
    else:
        scores = raw
    return {cls: scores[:, i].tolist() for i, cls in enumerate(classes)}


def run_cross_fitted_tone(
    annotation_df: pd.DataFrame,
    all_sentences_df: pd.DataFrame,
    n_splits: int = 5,
    seed: int = 2026,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cross-fit policy stance predictions across all guidance sentences.

    Parameters
    ----------
    annotation_df : labelled sentences with columns [annotation_id, report_id, section,
                    sentence, manual_policy_stance_label]
    all_sentences_df : ALL guidance-section sentences with columns [report_id, section,
                       sentence] (unlabelled portion to be predicted)
    """
    df = annotation_df.copy()
    df = df.dropna(subset=["manual_policy_stance_label", "sentence", "report_id"])
    labels = df["manual_policy_stance_label"].str.strip().str.lower()

    sentences = df["sentence"].tolist()
    report_ids = df["report_id"].astype(str).tolist()
    groups = make_report_duplicate_groups(sentences, report_ids)
    y_all = labels.to_numpy()
    _, counts = np.unique(y_all, return_counts=True)
    n_splits_eff = min(n_splits, len(set(groups)), int(counts.min()) if len(counts) else 0)
    if n_splits_eff < 2:
        raise ValueError("Too few labelled policy-stance samples for cross-fitting")

    sgkf = StratifiedGroupKFold(n_splits=n_splits_eff, shuffle=True, random_state=seed)
    X_all = np.array(sentences, dtype=object)

    all_sent = all_sentences_df.copy()
    all_sent = all_sent.dropna(subset=["report_id", "sentence"])
    all_sent = all_sent[all_sent["section"].astype(str).str.lower().eq("guidance")].copy()
    sent_rows = []
    for fold_idx, (train_idx, test_idx) in enumerate(sgkf.split(X_all, y_all, groups)):
        vectorizer = build_vectorizer()
        clf = build_classifier(C=1.0)
        X_train = vectorizer.fit_transform(np.array(sentences, dtype=object)[train_idx])
        y_train = y_all[train_idx]
        clf.fit(X_train, y_train)

        test_reports = sorted(set(df.iloc[test_idx]["report_id"].astype(str)))
        fold_sentences = all_sent[all_sent["report_id"].astype(str).isin(test_reports)].copy()
        if fold_sentences.empty:
            fold_sentences = df.iloc[test_idx].copy()
        X_test = vectorizer.transform(fold_sentences["sentence"].astype(str).to_numpy())
        y_pred = clf.predict(X_test)
        scores = _decision_scores(clf, X_test)

        labelled_lookup = {
            (str(row["report_id"]), str(row["sentence"])): str(row["manual_policy_stance_label"]).strip().lower()
            for _, row in df.iloc[test_idx].iterrows()
        }
        for i, (_, row) in enumerate(fold_sentences.iterrows()):
            true_label = labelled_lookup.get((str(row["report_id"]), str(row["sentence"])), "")
            score_dict = {f"decision_score_{cls}": scores[cls][i] for cls in scores}
            sent_rows.append({
                "annotation_id": row.get("annotation_id", f"{row['report_id']}_{row.get('sentence_id', i)}"),
                "report_id": row["report_id"],
                "fold": int(fold_idx),
                "sentence": row["sentence"],
                "true_label": true_label,
                "predicted_label": y_pred[i],
                **score_dict,
            })

    sent_preds = pd.DataFrame(sent_rows)

    # Report-level aggregation
    report_rows = []
    for report_id, grp in sent_preds.groupby("report_id"):
        # all_sentence_mean: average of dovish score minus hawkish score, across all sentences
        dovish_col = [c for c in grp.columns if "decision_score_dovish" in c]
        hawkish_col = [c for c in grp.columns if "decision_score_hawkish" in c]
        neutral_col = [c for c in grp.columns if "decision_score_neutral" in c]
        irrelevant_col = [c for c in grp.columns if "decision_score_irrelevant" in c]

        d_mean = grp[dovish_col[0]].mean() if dovish_col else np.nan
        h_mean = grp[hawkish_col[0]].mean() if hawkish_col else np.nan
        n_mean = grp[neutral_col[0]].mean() if neutral_col else np.nan
        i_mean = grp[irrelevant_col[0]].mean() if irrelevant_col else np.nan

        # policy_relevant: only sentences predicted as dovish/hawkish/neutral (excl irrelevant)
        policy_mask = grp["predicted_label"].isin(["dovish", "hawkish", "neutral"])
        d_policy = grp.loc[policy_mask, dovish_col[0]].mean() if dovish_col and policy_mask.sum() > 0 else np.nan
        h_policy = grp.loc[policy_mask, hawkish_col[0]].mean() if hawkish_col and policy_mask.sum() > 0 else np.nan

        # directional: only dovish/hawkish sentences
        dir_mask = grp["predicted_label"].isin(["dovish", "hawkish"])
        d_dir = grp.loc[dir_mask, dovish_col[0]].mean() if dovish_col and dir_mask.sum() > 0 else np.nan
        h_dir = grp.loc[dir_mask, hawkish_col[0]].mean() if hawkish_col and dir_mask.sum() > 0 else np.nan

        report_rows.append({
            "report_id": report_id,
            "all_sentence_mean": d_mean - h_mean if not (np.isnan(d_mean) or np.isnan(h_mean)) else np.nan,
            "policy_relevant_mean": d_policy - h_policy if not (np.isnan(d_policy) or np.isnan(h_policy)) else np.nan,
            "directional_sentence_mean": d_dir - h_dir if not (np.isnan(d_dir) or np.isnan(h_dir)) else np.nan,
            "n_sentences": int(len(grp)),
            "n_policy_relevant": int(policy_mask.sum()),
            "n_directional": int(dir_mask.sum()),
        })

    report_tone = pd.DataFrame(report_rows)
    return sent_preds, report_tone


def write_cross_fitted_outputs(sent_preds: pd.DataFrame, report_tone: pd.DataFrame) -> None:
    """Save cross-fitted outputs to processed data."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sent_preds.to_csv(PROCESSED_DIR / "cross_fitted_sentence_predictions.csv", index=False, encoding="utf-8-sig")
    report_tone.to_csv(PROCESSED_DIR / "cross_fitted_report_policy_tone.csv", index=False, encoding="utf-8-sig")
