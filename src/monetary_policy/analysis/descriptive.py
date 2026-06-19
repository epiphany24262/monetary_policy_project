from __future__ import annotations

import pandas as pd


def descriptive_stats(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    desc = df[cols].describe().T
    return desc[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]].reset_index(names="variable")

