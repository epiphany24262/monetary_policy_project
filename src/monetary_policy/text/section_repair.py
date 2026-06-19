from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..paths import OUTPUT_DIR, ROOT


REPAIR_RULES = {
    "2006Q1": {
        "start": r"二、下一阶段货币政策取向与趋势",
        "end": r"(专栏：|$)",
        "note": "正文第五部分第二节标题，目录中同名标题不使用；取最后一次匹配。",
    },
    "2006Q4": {
        "start": r"二、2007 年货币政策取向与趋势",
        "end": r"(图：|$)",
        "note": "正文第五部分第二节标题，取最后一次匹配。",
    },
    "2007Q2": {
        "start": r"二、下半年货币政策取向与趋势",
        "end": r"(专栏：|$)",
        "note": "正文第五部分第二节标题，取最后一次匹配。",
    },
    "2007Q4": {
        "start": r"三、2008 年货币政策取向",
        "end": r"(专栏：|$)",
        "note": "正文第五部分第三节标题，取最后一次匹配。",
    },
}


def _last_body_extract(text: str, start_pattern: str, end_pattern: str) -> tuple[str, str]:
    matches = list(re.finditer(start_pattern, text))
    if not matches:
        return "", "pattern_not_found"
    start = matches[-1].start()
    tail = text[start:]
    end_match = re.search(end_pattern, tail)
    end = len(tail) if not end_match or end_match.start() == 0 else end_match.start()
    extracted = tail[:end].strip()
    return extracted, "manual_title_alias_last_match"


def repair_guidance_sections() -> pd.DataFrame:
    sections = pd.read_csv(ROOT / "data/processed/report_sections.csv")
    rows = []
    for rid, rule in REPAIR_RULES.items():
        mask = (sections["report_id"] == rid) & (sections["section"] == "guidance")
        old = sections.loc[mask].iloc[0].to_dict()
        text_path = ROOT / "data/interim/report_text" / f"{rid}_clean_text.txt"
        text = text_path.read_text(encoding="utf-8", errors="ignore")
        extracted, extraction_rule = _last_body_extract(text, rule["start"], rule["end"])
        local_path = ROOT / str(old["local_path"])
        new_found = len(extracted) >= 200
        if new_found:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(extracted, encoding="utf-8")
            sections.loc[mask, "found"] = True
            sections.loc[mask, "char_count"] = len(extracted)
            sections.loc[mask, "word_count_proxy"] = max(1, len(extracted) // 8)
        rows.append(
            {
                "report_id": rid,
                "old_found": bool(old["found"]),
                "old_char_count": int(old["char_count"]),
                "new_found": bool(new_found),
                "new_char_count": len(extracted),
                "extraction_rule": extraction_rule,
                "manual_override": True,
                "review_note": rule["note"],
            }
        )
    out_path = ROOT / "data/processed/report_sections_repaired.csv"
    sections.to_csv(out_path, index=False, encoding="utf-8-sig")
    report = pd.DataFrame(rows)
    diag_dir = OUTPUT_DIR / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    report.to_excel(diag_dir / "section_repair_report.xlsx", index=False)
    return sections


def load_repaired_or_original_sections() -> pd.DataFrame:
    repaired = ROOT / "data/processed/report_sections_repaired.csv"
    if repaired.exists():
        return pd.read_csv(repaired)
    return pd.read_csv(ROOT / "data/processed/report_sections.csv")
