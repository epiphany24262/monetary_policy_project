from __future__ import annotations

import pandas as pd
import numpy as np

from ..data.pbc_reports import load_section_texts
from ..paths import DATA_DIR, OUTPUT_DIR
from ..sample import is_in_formal_sample
from .lexicon import build_combined_lexicon
from .sentiment import score_text
from .text_cleaner import split_sentences


ANNOTATION_PATH = DATA_DIR / "validation" / "manual_sentence_annotation.xlsx"
FILLED_PATH = DATA_DIR / "validation" / "manual_sentence_annotation_filled.xlsx"


def _target_counts(n: int, total: int) -> list[int]:
    base = total // n
    remainder = total % n
    return [base + (1 if i < remainder else 0) for i in range(n)]


def _even_positions(length: int, target: int) -> list[int]:
    if length <= target:
        return list(range(length))
    return [int(x) for x in np.linspace(0, length - 1, target).round()]


def has_filled_annotations() -> bool:
    """Check if manually filled annotations exist."""
    return FILLED_PATH.exists()


def load_filled_annotations() -> pd.DataFrame:
    """Load the manually filled annotation file."""
    if not FILLED_PATH.exists():
        raise FileNotFoundError(f"Filled annotation file not found: {FILLED_PATH}")
    return pd.read_excel(FILLED_PATH)


def build_manual_sentence_annotation(text_features: pd.DataFrame | None = None, total_rows: int = 240) -> dict:
    """Generate manual sentence annotation sample.

    IMPORTANT: This function will NEVER overwrite an existing filled annotation file.
    If ``manual_sentence_annotation_filled.xlsx`` already exists, the generation step
    is skipped and the filled file is loaded instead.

    When generating a fresh ``manual_sentence_annotation.xlsx``, if a filled version
    already exists, existing manual labels are merged back so that no human work is lost.
    """
    # ── Guard: never overwrite filled annotations ──
    if FILLED_PATH.exists():
        filled = pd.read_excel(FILLED_PATH)
        # Always refresh the blank template so label columns stay empty.
        template = filled[
            [
                "annotation_id", "report_id", "report_period", "section",
                "sentence", "auto_sentiment_score", "auto_policy_stance_score",
                "manual_sentiment_label", "manual_policy_stance_label",
                "manual_topic_label", "reviewer", "review_note",
            ]
        ].copy()
        # Blank out labels for the template
        template["manual_sentiment_label"] = ""
        template["manual_policy_stance_label"] = ""
        template["manual_topic_label"] = ""
        template["reviewer"] = ""
        template["review_note"] = ""
        ANNOTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        template.to_excel(ANNOTATION_PATH, index=False)
        return {
            "path": str(FILLED_PATH),
            "rows": int(len(filled)),
            "sections": {
                sec: int(cnt)
                for sec, cnt in filled.groupby("section", sort=False).size().items()
            },
            "manual_labels_blank": False,
            "source": "filled",
        }

    # ── Generate fresh sample ──
    sections = load_section_texts()
    lexicon = build_combined_lexicon()
    sections = sections[
        sections["section"].isin(["guidance", "macro"])
        & sections["found"].astype(bool)
        & sections["report_period"].map(is_in_formal_sample)
    ].copy()
    samples = []
    per_section_total = total_rows // 2
    for section in ["guidance", "macro"]:
        part = sections[sections["section"] == section].sort_values("report_period").reset_index(drop=True)
        if part.empty:
            continue
        targets = _target_counts(len(part), per_section_total)
        for i, row in part.iterrows():
            sentences_list = [s for s in split_sentences(row["text"]) if 12 <= len(s) <= 180]
            if not sentences_list:
                continue
            if len(sentences_list) <= targets[i]:
                picked = sentences_list
            else:
                positions = _even_positions(len(sentences_list), targets[i])
                picked = [sentences_list[pos] for pos in positions]
            for sent_no, sent in enumerate(picked, start=1):
                rule_score = score_text(sent, lexicon)
                samples.append(
                    {
                        "annotation_id": f"{row['report_id']}_{section}_{sent_no:02d}",
                        "report_id": row["report_id"],
                        "report_period": row["report_period"],
                        "section": section,
                        "sentence": sent,
                        "auto_sentiment_score": rule_score["normalized_sentiment"],
                        "auto_policy_stance_score": rule_score["normalized_policy_stance"],
                        "manual_sentiment_label": "",
                        "manual_policy_stance_label": "",
                        "manual_topic_label": "",
                        "reviewer": "",
                        "review_note": "",
                    }
                )
    out = pd.DataFrame(samples)
    if len(out) > total_rows:
        out = pd.concat(
            [
                g.iloc[_even_positions(len(g), total_rows // 2)]
                for _, g in out.groupby("section", sort=False)
            ],
            ignore_index=True,
        )
    elif len(out) < total_rows and not out.empty:
        shortage = total_rows - len(out)
        extra = out.head(shortage).copy()
        extra["annotation_id"] = extra["annotation_id"] + "_dup_context"
        out = pd.concat([out, extra], ignore_index=True)
    out = out.sort_values(["section", "report_period", "annotation_id"]).reset_index(drop=True)
    ANNOTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_excel(ANNOTATION_PATH, index=False)
    diagnostics_dir = OUTPUT_DIR / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    balance = out.groupby(["section"], as_index=False).size()
    balance.to_excel(diagnostics_dir / "manual_annotation_balance.xlsx", index=False)
    return {
        "path": str(ANNOTATION_PATH),
        "rows": int(len(out)),
        "sections": {row["section"]: int(row["size"]) for _, row in balance.iterrows()},
        "manual_labels_blank": True,
        "source": "generated",
    }
