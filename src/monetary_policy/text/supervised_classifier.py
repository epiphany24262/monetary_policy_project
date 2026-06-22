"""Char TF-IDF + LinearSVC with grouped cross-validation."""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline

SEEDS = [42, 2026, 3407]


def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        min_df=1,
        max_features=8000,
        sublinear_tf=True,
    )


def build_classifier(C: float = 1.0) -> LinearSVC:
    return LinearSVC(
        class_weight="balanced",
        C=C,
        max_iter=5000,
        dual=True,
        random_state=2026,
    )


def _normalise_sentence(sentence: str) -> str:
    return re.sub(r"\s+|[，。、“”‘’：；（）()《》〈〉,.!?！？:;\"']", "", str(sentence))


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    if len(text) <= n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _near_duplicate(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted([a, b], key=len)
    if len(shorter) >= 20 and shorter in longer:
        return True
    grams_a = _char_ngrams(a)
    grams_b = _char_ngrams(b)
    if not grams_a or not grams_b:
        return False
    return len(grams_a & grams_b) / len(grams_a | grams_b) >= 0.92


def make_report_duplicate_groups(sentences: list[str], report_ids: list[str]) -> list[str]:
    """Combine report-level grouping with near-duplicate sentence grouping.

    Rows from the same report must stay in the same fold.  Near-duplicate
    sentences that recur across reports are also unioned into the same fold,
    preventing formulaic PBC phrases from leaking across train and test.
    """
    n = len(sentences)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_report: dict[str, int] = {}
    for i, report_id in enumerate(report_ids):
        key = str(report_id)
        if key in by_report:
            union(i, by_report[key])
        else:
            by_report[key] = i

    normalised = [_normalise_sentence(s) for s in sentences]
    for i in range(n):
        for j in range(i + 1, n):
            if _near_duplicate(normalised[i], normalised[j]):
                union(i, j)

    labels = []
    for i in range(n):
        root = find(i)
        digest = hashlib.sha1(f"{root}:{report_ids[root]}:{normalised[root][:80]}".encode("utf-8")).hexdigest()[:12]
        labels.append(f"grp_{digest}")
    return labels


def _build_pipeline(C: float) -> Pipeline:
    return Pipeline([("tfidf", build_vectorizer()), ("clf", build_classifier(C=C))])


def grouped_cross_validate(
    sentences: list[str],
    labels: list[str],
    groups: list[str],
    C: float = 1.0,
    seed: int = 2026,
    n_splits: int = 5,
) -> dict:
    """StratifiedGroupKFold with report and near-duplicate groups.

    Returns predictions, metrics, and per-fold results.
    """
    X_raw = np.array(sentences, dtype=object)
    y = np.array(labels, dtype=str)
    groups_arr = np.array(make_report_duplicate_groups(sentences, groups), dtype=str)

    unique, counts = np.unique(y, return_counts=True)
    min_class_count = int(counts.min()) if len(counts) else 0
    n_splits_eff = min(int(n_splits), len(set(groups_arr)), min_class_count)
    if n_splits_eff < 2 or len(X_raw) < 4:
        return {
            "error": "Too few samples or groups for grouped cross-validation",
            "n": int(len(X_raw)),
            "min_class_count": min_class_count,
            "n_groups": int(len(set(groups_arr))),
        }

    sgkf = StratifiedGroupKFold(n_splits=n_splits_eff, shuffle=True, random_state=seed)

    y_pred = np.empty_like(y, dtype=object)
    fold_rows = []
    for fold, (train_idx, test_idx) in enumerate(sgkf.split(X_raw, y, groups_arr)):
        model = _build_pipeline(C)
        model.fit(X_raw[train_idx], y[train_idx])
        fold_pred = model.predict(X_raw[test_idx])
        y_pred[test_idx] = fold_pred
        fold_rows.append(
            {
                "fold": int(fold),
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "train_groups": int(len(set(groups_arr[train_idx]))),
                "test_groups": int(len(set(groups_arr[test_idx]))),
                "train_labels": sorted(set(y[train_idx])),
                "test_labels": sorted(set(y[test_idx])),
            }
        )

    labels_used = sorted(set(y) | set(y_pred))
    report = classification_report(y, y_pred, labels=labels_used, output_dict=True, zero_division=0)
    acc = float(accuracy_score(y, y_pred))
    macro_f1 = float(f1_score(y, y_pred, average="macro", zero_division=0))

    cm = confusion_matrix(y, y_pred, labels=labels_used)

    return {
        "n": int(len(X_raw)),
        "n_groups": int(len(set(groups_arr))),
        "n_splits": int(n_splits_eff),
        "n_features": int(_build_pipeline(C).fit(X_raw, y).named_steps["tfidf"].transform(X_raw).shape[1]),
        "accuracy": acc,
        "macro_f1": macro_f1,
        "labels": labels_used,
        "classification_report": {k: {kk: float(vv) if isinstance(vv, (int, float, np.floating)) else vv
                                      for kk, vv in v.items()}
                                 for k, v in report.items() if isinstance(v, dict)},
        "confusion_matrix": cm.tolist(),
        "folds": fold_rows,
        "predictions": [
            {
                "sentence": str(X_raw[i]),
                "group": str(groups_arr[i]),
                "true_label": str(y[i]),
                "predicted_label": str(y_pred[i]),
            }
            for i in range(len(X_raw))
        ],
        "C": C,
        "seed": seed,
    }


def generate_learning_curve(
    sentences: list[str],
    labels: list[str],
    groups: list[str],
    C: float = 1.0,
    seed: int = 2026,
    train_ratios: list[float] | None = None,
) -> pd.DataFrame:
    """Learning curve across training ratios with grouped train subsets."""
    if train_ratios is None:
        train_ratios = [0.25, 0.40, 0.60, 0.80, 1.00]

    X_raw = np.array(sentences, dtype=object)
    y = np.array(labels, dtype=str)
    groups_arr = np.array(make_report_duplicate_groups(sentences, groups), dtype=str)
    unique, counts = np.unique(y, return_counts=True)
    n_splits_eff = min(5, len(set(groups_arr)), int(counts.min()) if len(counts) else 0)
    if n_splits_eff < 2:
        return pd.DataFrame(
            [{"train_ratio": ratio, "accuracy": np.nan, "macro_f1": np.nan, "n": len(X_raw), "error": "Too few samples or groups"} for ratio in train_ratios]
        )

    sgkf = StratifiedGroupKFold(n_splits=n_splits_eff, shuffle=True, random_state=seed)
    rng = np.random.default_rng(seed)
    rows = []
    for ratio in train_ratios:
        y_true_all = []
        y_pred_all = []
        train_sizes = []
        fold_count = 0
        for train_idx, test_idx in sgkf.split(X_raw, y, groups_arr):
            train_groups = np.array(sorted(set(groups_arr[train_idx])), dtype=object)
            rng.shuffle(train_groups)
            target_group_count = max(1, int(np.ceil(len(train_groups) * ratio)))
            selected = set(train_groups[:target_group_count])
            sub_train_idx = np.array([i for i in train_idx if groups_arr[i] in selected], dtype=int)
            while len(set(y[sub_train_idx])) < 2 and target_group_count < len(train_groups):
                target_group_count += 1
                selected = set(train_groups[:target_group_count])
                sub_train_idx = np.array([i for i in train_idx if groups_arr[i] in selected], dtype=int)
            if len(sub_train_idx) < 3 or len(set(y[sub_train_idx])) < 2:
                continue
            model = _build_pipeline(C)
            model.fit(X_raw[sub_train_idx], y[sub_train_idx])
            y_true_all.extend(y[test_idx].tolist())
            y_pred_all.extend(model.predict(X_raw[test_idx]).tolist())
            train_sizes.append(int(len(sub_train_idx)))
            fold_count += 1
        if not y_true_all:
            rows.append({"train_ratio": ratio, "accuracy": np.nan, "macro_f1": np.nan, "n": 0, "train_n_mean": np.nan, "folds": 0, "error": "No valid folds"})
            continue
        rows.append(
            {
                "train_ratio": ratio,
                "accuracy": float(accuracy_score(y_true_all, y_pred_all)),
                "macro_f1": float(f1_score(y_true_all, y_pred_all, average="macro", zero_division=0)),
                "n": int(len(y_true_all)),
                "train_n_mean": float(np.mean(train_sizes)),
                "folds": int(fold_count),
                "error": None,
            }
        )
    return pd.DataFrame(rows)
