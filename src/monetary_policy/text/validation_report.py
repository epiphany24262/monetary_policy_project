"""Text validation against manual annotations."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from .lexicon import build_combined_lexicon
from .lexicon import COMBINED_PATH
from .sentiment import score_text
from .context_gate import gate_stance_label, load_context_rules
from ..paths import FIGURES_DIR, OUTPUT_DIR


def _auto_sentiment_label(score: float) -> str:
    if pd.isna(score) or score == 0:
        return "neutral"
    return "positive" if score > 0 else "negative"


def _auto_stance_label(score: float) -> str:
    if pd.isna(score) or score == 0:
        return "neutral"
    return "dovish" if score > 0 else "hawkish"


def _auto_topic_label(attention: dict[str, float]) -> str:
    topics = ["growth", "inflation", "risk", "exchange_rate", "financial_stability", "real_estate"]
    best = max(topics, key=lambda t: attention.get(f"attention_{t}", 0.0))
    return best if attention.get(f"attention_{best}", 0.0) > 0 else "other"



def run_text_validation(annotation_path: Path | None = None) -> dict:
    from ..paths import DATA_DIR

    if annotation_path is None:
        annotation_path = DATA_DIR / "validation" / "manual_sentence_annotation_filled.xlsx"

    if not annotation_path.exists():
        raise FileNotFoundError(f"Filled annotation file not found: {annotation_path}")

    df = pd.read_excel(annotation_path)

    lexicon = build_combined_lexicon()
    context_rules = load_context_rules()
    rescored = [score_text(str(sentence), lexicon) for sentence in df["sentence"]]
    df["current_auto_sentiment_score"] = [row["normalized_sentiment"] for row in rescored]
    df["current_auto_policy_stance_score"] = [row["normalized_policy_stance"] for row in rescored]
    df["auto_sentiment"] = df["current_auto_sentiment_score"].map(_auto_sentiment_label)
    df["auto_stance_signed"] = df["current_auto_policy_stance_score"].map(_auto_stance_label)
    df["auto_stance"] = [
        gate_stance_label(label, str(sentence), context_rules)
        for label, sentence in zip(df["auto_stance_signed"], df["sentence"])
    ]
    df["auto_topic"] = [_auto_topic_label(row) for row in rescored]

    stored_sentiment_mismatch = int(
        (~np.isclose(
            pd.to_numeric(df.get("auto_sentiment_score"), errors="coerce"),
            df["current_auto_sentiment_score"],
            equal_nan=True,
        )).sum()
    ) if "auto_sentiment_score" in df.columns else 0
    stored_stance_mismatch = int(
        (~np.isclose(
            pd.to_numeric(df.get("auto_policy_stance_score"), errors="coerce"),
            df["current_auto_policy_stance_score"],
            equal_nan=True,
        )).sum()
    ) if "auto_policy_stance_score" in df.columns else 0

    # ── Standardize manual labels ──
    df["manual_sentiment"] = df["manual_sentiment_label"].str.strip().str.lower()
    df["manual_stance"] = df["manual_policy_stance_label"].str.strip().str.lower()
    df["manual_topic"] = df["manual_topic_label"].str.strip().str.lower()

    # ── Validate field completeness ──
    required = [
        "manual_sentiment_label",
        "manual_policy_stance_label",
        "manual_topic_label",
        "reviewer",
    ]
    completeness = {}
    for col in required:
        nulls = df[col].isna().sum()
        empties = (df[col].astype(str).str.strip() == "").sum()
        completeness[col] = {"null": int(nulls), "empty_string": int(empties), "valid": int(len(df) - nulls - empties)}

    # ── Validate label values ──
    valid_sentiment = {"positive", "negative", "neutral"}
    valid_stance = {"dovish", "hawkish", "neutral", "irrelevant"}
    valid_topic = {"growth", "inflation", "risk", "exchange_rate", "financial_stability", "other", "real_estate"}

    illegal = {}
    illegal["sentiment"] = sorted(set(df["manual_sentiment"]) - valid_sentiment)
    illegal["stance"] = sorted(set(df["manual_stance"]) - valid_stance)
    illegal["topic"] = sorted(set(df["manual_topic"]) - valid_topic)

    # ── Metrics for each task ──
    policy_relevant = df["manual_stance"] != "irrelevant"
    tasks = {
        "sentiment": {
            "y_true": df["manual_sentiment"],
            "y_pred": df["auto_sentiment"],
            "labels": ["positive", "negative", "neutral"],
        },
        # Backward-compatible full four-class view.  The lexicon score itself
        # does not model the separate relevance/irrelevance decision, so this
        # metric is expected to be low and is retained as a diagnostic only.
        "policy_stance": {
            "y_true": df["manual_stance"],
            "y_pred": df["auto_stance"],
            "labels": ["dovish", "hawkish", "neutral", "irrelevant"],
        },
        # Directional performance on sentences manually judged policy-relevant.
        # This is the fair evaluation of the signed stance score.
        "policy_direction": {
            "y_true": df.loc[policy_relevant, "manual_stance"],
            "y_pred": df.loc[policy_relevant, "auto_stance"],
            "labels": ["dovish", "hawkish", "neutral"],
        },
        "topic": {
            "y_true": df["manual_topic"],
            "y_pred": df["auto_topic"],
            "labels": sorted(set(df["manual_topic"].unique()) | set(df["auto_topic"].unique())),
        },
    }

    results = {}
    for task_name, task in tasks.items():
        y_true = task["y_true"]
        y_pred = task["y_pred"]
        labels = task["labels"]

        # Filter to labels present in data
        present_labels = sorted(set(y_true.unique()) | set(y_pred.unique()))
        labels_used = [l for l in labels if l in present_labels]

        acc = float(accuracy_score(y_true, y_pred))
        macro_f1 = float(f1_score(y_true, y_pred, average="macro", labels=labels_used, zero_division=0))
        weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", labels=labels_used, zero_division=0))

        prec, rec, f1, support = precision_recall_fscore_support(
            y_true, y_pred, labels=labels_used, zero_division=0
        )

        cls_report = []
        for i, lbl in enumerate(labels_used):
            cls_report.append({
                "class": lbl,
                "precision": float(prec[i]),
                "recall": float(rec[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            })

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred, labels=labels_used)

        results[task_name] = {
            "n": int(len(y_true)),
            "accuracy": acc,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
            "labels_used": labels_used,
            "class_report": cls_report,
            "confusion_matrix": cm.tolist(),
        }

    # ── Disagreements ──
    disagrees = df[
        (df["auto_sentiment"] != df["manual_sentiment"])
        | (df["auto_stance"] != df["manual_stance"])
        | (df["auto_topic"] != df["manual_topic"])
    ].copy()
    disagrees["disagree_sentiment"] = disagrees["auto_sentiment"] != disagrees["manual_sentiment"]
    disagrees["disagree_stance"] = disagrees["auto_stance"] != disagrees["manual_stance"]
    disagrees["disagree_topic"] = disagrees["auto_topic"] != disagrees["manual_topic"]

    # ── Summary ──
    n_disagree_sent = int(disagrees["disagree_sentiment"].sum())
    n_disagree_stance = int(disagrees["disagree_stance"].sum())
    n_disagree_topic = int(disagrees["disagree_topic"].sum())
    annotation_sha = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
    lexicon_sha = hashlib.sha256(COMBINED_PATH.read_bytes()).hexdigest() if COMBINED_PATH.exists() else ""

    summary = {
        "total_sentences": int(len(df)),
        "annotation_path": str(annotation_path),
        "annotation_sha256": annotation_sha,
        "lexicon_path": str(COMBINED_PATH),
        "lexicon_sha256": lexicon_sha,
        "completeness": completeness,
        "illegal_labels": illegal,
        "sentiment_accuracy": results["sentiment"]["accuracy"],
        "sentiment_macro_f1": results["sentiment"]["macro_f1"],
        "sentiment_weighted_f1": results["sentiment"]["weighted_f1"],
        "stance_accuracy": results["policy_stance"]["accuracy"],
        "stance_macro_f1": results["policy_stance"]["macro_f1"],
        "stance_weighted_f1": results["policy_stance"]["weighted_f1"],
        "policy_direction_accuracy": results["policy_direction"]["accuracy"],
        "policy_direction_macro_f1": results["policy_direction"]["macro_f1"],
        "policy_direction_weighted_f1": results["policy_direction"]["weighted_f1"],
        "score_source": "current_lexicon_rescore",
        "context_gate": "pbc_context_rules_v1",
        "context_gate_changed_count": int((df["auto_stance"] != df["auto_stance_signed"]).sum()),
        "lexicon_version": int(getattr(lexicon, "version", 0)),
        "stored_sentiment_score_mismatch_count": stored_sentiment_mismatch,
        "stored_stance_score_mismatch_count": stored_stance_mismatch,
        "topic_accuracy": results["topic"]["accuracy"],
        "topic_macro_f1": results["topic"]["macro_f1"],
        "topic_weighted_f1": results["topic"]["weighted_f1"],
        "disagreement_count": int(len(disagrees)),
        "disagreement_sentiment_count": n_disagree_sent,
        "disagreement_stance_count": n_disagree_stance,
        "disagreement_topic_count": n_disagree_topic,
        "systematic_issue_detected": (
            results["sentiment"]["accuracy"] < 0.7
            or results["policy_stance"]["macro_f1"] < 0.3
            or results["topic"]["accuracy"] < 0.5
        ),
    }

    return {
        "sentiment": results["sentiment"],
        "policy_stance": results["policy_stance"],
        "policy_direction": results["policy_direction"],
        "topic": results["topic"],
        "disagreements": disagrees,
        "summary": summary,
    }



def write_validation_outputs(validation: dict) -> dict[str, Path]:
    """Write all validation diagnostics: Excel, Markdown report, confusion matrix PNGs."""
    diag = OUTPUT_DIR / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    output_paths = {}

    # ── 1. Excel metrics ──
    xlsx_path = diag / "text_validation_metrics.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for task_name in ["sentiment", "policy_stance", "policy_direction", "topic"]:
            task = validation[task_name]
            # Class-level
            pd.DataFrame(task["class_report"]).to_excel(
                writer, sheet_name=f"{task_name}_classes"[:31], index=False
            )
            # Confusion matrix
            cm_df = pd.DataFrame(
                task["confusion_matrix"],
                index=task["labels_used"],
                columns=task["labels_used"],
            )
            cm_df.to_excel(writer, sheet_name=f"{task_name}_cm"[:31])
        # Summary
        pd.DataFrame([validation["summary"]]).to_excel(writer, sheet_name="summary", index=False)
    output_paths["metrics_xlsx"] = xlsx_path

    # ── 2. Disagreements Excel ──
    disagree_path = diag / "text_label_disagreements.xlsx"
    dis_cols = [
        "annotation_id", "report_id", "report_period", "section", "sentence",
        "auto_sentiment_score", "current_auto_sentiment_score",
        "auto_sentiment", "manual_sentiment",
        "auto_policy_stance_score", "current_auto_policy_stance_score",
        "auto_stance_signed", "auto_stance", "manual_stance",
        "auto_topic", "manual_topic",
        "disagree_sentiment", "disagree_stance", "disagree_topic",
    ]
    validation["disagreements"][dis_cols].to_excel(disagree_path, index=False)
    output_paths["disagreements_xlsx"] = disagree_path

    # ── 3. Markdown report ──
    md = _build_markdown_report(validation)
    md_path = diag / "text_validation_report.md"
    md_path.write_text(md, encoding="utf-8")
    output_paths["report_md"] = md_path

    # ── 4. Confusion matrix PNGs ──
    cm_configs = [
        ("sentiment", "figure_sentiment_confusion_matrix.png", "Sentiment Confusion Matrix"),
        ("policy_stance", "figure_policy_confusion_matrix.png", "Policy Stance Confusion Matrix"),
        ("policy_direction", "figure_policy_direction_confusion_matrix.png", "Policy Direction Confusion Matrix"),
        ("topic", "figure_topic_confusion_matrix.png", "Topic Confusion Matrix"),
    ]
    for task_name, filename, title_en in cm_configs:
        cm_path = FIGURES_DIR / filename
        _plot_confusion_matrix(
            validation[task_name]["confusion_matrix"],
            validation[task_name]["labels_used"],
            title_en,
            cm_path,
        )
        output_paths[f"cm_{task_name}"] = cm_path

    return output_paths


def _build_markdown_report(validation: dict) -> str:
    s = validation["summary"]
    lines = [
        "# 文本验证报告 — 自动词典标签 vs 人工标注",
        "",
        f"**总句子数**: {s['total_sentences']}",
        f"**不一致句子数**: {s['disagreement_count']}",
        "",
        "## 字段完整性",
        "",
        "| 字段 | 空值 | 空字符串 | 有效 |",
        "|------|------|----------|------|",
    ]
    for col, info in s["completeness"].items():
        lines.append(f"| {col} | {info['null']} | {info['empty_string']} | {info['valid']} |")

    illegal = s["illegal_labels"]
    if any(illegal.values()):
        lines.append("")
        lines.append("## ⚠ 非法标签值")
        for task_name, vals in illegal.items():
            if vals:
                lines.append(f"- **{task_name}**: {vals}")

    lines.extend([
        "",
        "## 总体指标",
        "",
        "| 任务 | Accuracy | Macro-F1 | Weighted-F1 |",
        "|------|----------|----------|-------------|",
        f"| 情感 | {s['sentiment_accuracy']:.4f} | {s['sentiment_macro_f1']:.4f} | {s['sentiment_weighted_f1']:.4f} |",
        f"| 政策倾向（四分类诊断） | {s['stance_accuracy']:.4f} | {s['stance_macro_f1']:.4f} | {s['stance_weighted_f1']:.4f} |",
        f"| 政策方向（仅相关句） | {s['policy_direction_accuracy']:.4f} | {s['policy_direction_macro_f1']:.4f} | {s['policy_direction_weighted_f1']:.4f} |",
        f"| 主题 | {s['topic_accuracy']:.4f} | {s['topic_macro_f1']:.4f} | {s['topic_weighted_f1']:.4f} |",
        "",
        "## 系统性错误判断",
        "",
    ])

    if s["systematic_issue_detected"]:
        lines.append("⚠ **检测到潜在系统性错误**。详见下文分析。")
    else:
        lines.append("✅ 未检测到明显系统性错误。零星误判在词典方法预期范围内。")

    for task_name in ["sentiment", "policy_stance", "policy_direction", "topic"]:
        task = validation[task_name]
        lines.extend([
            "",
            f"### {task_name} — 各类别指标 (n={task['n']})",
            "",
            f"Accuracy: {task['accuracy']:.4f}  |  Macro-F1: {task['macro_f1']:.4f}  |  Weighted-F1: {task['weighted_f1']:.4f}",
            "",
            "| 类别 | Precision | Recall | F1 | Support |",
            "|------|-----------|--------|----|---------|",
        ])
        for row in task["class_report"]:
            lines.append(
                f"| {row['class']} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | {row['support']} |"
            )

    # Disagreement summary
    lines.extend([
        "",
        "## 不一致统计",
        "",
        f"- 情感不一致: {s['disagreement_sentiment_count']} 句",
        f"- 政策倾向不一致: {s['disagreement_stance_count']} 句",
        f"- 主题不一致: {s['disagreement_topic_count']} 句",
        "",
        "完整不一致清单见 `text_label_disagreements.xlsx`。",
    ])

    return "\n".join(lines) + "\n"


def _plot_confusion_matrix(
    cm: list[list[int]],
    labels: list[str],
    title: str,
    path: Path,
) -> None:
    """Plot and save a confusion matrix heatmap."""
    cm_arr = np.array(cm)
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), max(5, len(labels) * 1.0)))
    im = ax.imshow(cm_arr, cmap="Blues", aspect="auto")

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Auto (predicted)", fontsize=10)
    ax.set_ylabel("Manual (true)", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold")

    # Annotate cells
    for i in range(cm_arr.shape[0]):
        for j in range(cm_arr.shape[1]):
            ax.text(j, i, str(cm_arr[i, j]), ha="center", va="center",
                    fontsize=10, color="white" if cm_arr[i, j] > cm_arr.max() / 2 else "black")

    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
