from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import get_path_config
from ..paths import ROOT, root_relative_path


def load_report_metadata() -> pd.DataFrame:
    df = pd.read_csv(ROOT / get_path_config("pbc_metadata"))
    df["publication_datetime"] = pd.to_datetime(df["publication_datetime"])
    return df.sort_values("publication_datetime").reset_index(drop=True)


def load_report_sections() -> pd.DataFrame:
    repaired = ROOT / "data/processed/report_sections_repaired.csv"
    if repaired.exists():
        df = pd.read_csv(repaired)
    else:
        df = pd.read_csv(ROOT / get_path_config("report_sections"))
    if "local_path" in df.columns:
        df["local_path"] = df["local_path"].astype(str).str.replace("\\", "/", regex=False)
    return df


def report_text_path(report_id: str) -> Path:
    return ROOT / get_path_config("report_text_dir") / f"{report_id}_clean_text.txt"


def load_full_texts() -> pd.DataFrame:
    rows = []
    for _, row in load_report_metadata().iterrows():
        path = report_text_path(row["report_id"])
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        rows.append(
            {
                "report_id": row["report_id"],
                "report_period": row["report_period"],
                "publication_datetime": row["publication_datetime"],
                "section": "full",
                "text": text,
                "char_count": len(text),
            }
        )
    return pd.DataFrame(rows)


def load_section_texts() -> pd.DataFrame:
    sections = load_report_sections()
    rows = []
    for _, row in sections.iterrows():
        path = root_relative_path(row["local_path"])
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        rows.append({**row.to_dict(), "text": text})
    return pd.DataFrame(rows)
