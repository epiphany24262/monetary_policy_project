"""Generate final_table_value_mapping.csv from the already-saved table CSVs.

Reads the journal_table*.csv files in output/tables/ (which are the exact data
fed into the paper builder), then writes every expected cell value into a
canonical mapping CSV for downstream PDF validation (Correction 1).
"""
from __future__ import annotations
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = ROOT / "output" / "tables"

import pandas as pd

LOOKS_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _looks_numeric(value: str) -> bool:
    return bool(LOOKS_NUMERIC_RE.match(str(value).strip()))


def _panel_columns(panel_df: pd.DataFrame) -> list[str]:
    candidates = [c for c in panel_df.columns if c != "Panel"]
    columns = []
    for column in candidates:
        values = panel_df[column].astype(str).str.strip()
        if values.ne("—").any() and values.ne("").any():
            columns.append(column)
    return columns


def generate_mapping():
    table_specs = [
        ("表1", "table1", "journal_table1_data_sources.csv", False),
        ("表2", "table2", "journal_table2_text_measurement.csv", True),
        ("表3", "table3", "journal_table3_stock_volatility.csv", False),
        ("表4", "table4", "journal_table4_robustness_egarch.csv", False),
        ("表5", "table5", "journal_table5_exploration_bond.csv", True),
    ]

    rows_out = []
    for caption, base_key, csv_name, is_panel in table_specs:
        csv_path = TABLES_DIR / csv_name
        if not csv_path.exists():
            print(f"WARNING: {csv_path} not found, skipping")
            continue
        df = pd.read_csv(csv_path, encoding="utf-8-sig")

        if is_panel and "Panel" in df.columns:
            for panel_name, panel_df in df.groupby("Panel", sort=False):
                panel_key = f"{base_key}_panel_a" if "Panel A" in str(panel_name) else f"{base_key}_panel_b"
                columns = _panel_columns(panel_df)
                table_rows = [columns] + panel_df[columns].astype(str).values.tolist()
                _emit_rows(rows_out, caption, panel_key, str(panel_name), table_rows)
        else:
            table_rows = [list(df.columns)] + df.astype(str).values.tolist()
            _emit_rows(rows_out, caption, base_key, "", table_rows)

    out_path = ROOT / "output" / "diagnostics" / "final_table_value_mapping.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "table_caption", "semantic_key", "panel", "row_index",
            "col_index", "header", "row_label", "expected_display_value",
            "value_type",
        ])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Wrote {len(rows_out)} mapped values to {out_path}")
    return out_path


def _emit_rows(rows_out, caption, semantic_key, panel, table_rows):
    headers = table_rows[0]
    for i, row_vals in enumerate(table_rows):
        if i == 0:
            continue  # skip header row
        row_label = str(row_vals[0]).strip() if row_vals else ""
        for j, value in enumerate(row_vals):
            value_str = str(value).strip()
            if not value_str or value_str == "—" or value_str == "nan":
                continue
            vtype = "numeric" if _looks_numeric(value_str) else "text"
            rows_out.append({
                "table_caption": caption,
                "semantic_key": semantic_key,
                "panel": panel,
                "row_index": i,
                "col_index": j,
                "header": headers[j] if j < len(headers) else "",
                "row_label": row_label,
                "expected_display_value": value_str,
                "value_type": vtype,
            })


if __name__ == "__main__":
    generate_mapping()
