from __future__ import annotations

import hashlib
import re

import pandas as pd

from .config import load_config
from .paths import RESEARCH_DIR


PERIOD_RE = re.compile(r"^(\d{4})Q([1-4])$")


def period_key(value: str) -> tuple[int, int]:
    match = PERIOD_RE.match(str(value))
    if not match:
        raise ValueError(f"Invalid report period: {value}")
    return int(match.group(1)), int(match.group(2))


def is_in_formal_sample(period: str) -> bool:
    cfg = load_config()["analysis_sample"]
    return period_key(cfg["start_period"]) <= period_key(period) <= period_key(cfg["end_period"])


def filter_formal_sample(df: pd.DataFrame, period_col: str = "report_period") -> pd.DataFrame:
    return df[df[period_col].map(is_in_formal_sample)].copy()


def post_2019(period: str) -> int:
    return int(period_key(period) >= (2019, 1))


def sample_bounds() -> tuple[str, str]:
    cfg = load_config()["analysis_sample"]
    return cfg["start_period"], cfg["end_period"]


def verify_final_analysis_plan() -> None:
    plan = RESEARCH_DIR / "FINAL_ANALYSIS_PLAN.md"
    sha_path = RESEARCH_DIR / "FINAL_ANALYSIS_PLAN.sha256"
    if not plan.exists() or not sha_path.exists():
        raise FileNotFoundError("Missing locked FINAL_ANALYSIS_PLAN.md or FINAL_ANALYSIS_PLAN.sha256")
    expected = sha_path.read_text(encoding="utf-8").strip().split()[0]
    actual = hashlib.sha256(plan.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if actual != expected:
        raise RuntimeError(
            "FINAL_ANALYSIS_PLAN.md hash mismatch. Do not continue until the plan is intentionally re-locked."
        )
