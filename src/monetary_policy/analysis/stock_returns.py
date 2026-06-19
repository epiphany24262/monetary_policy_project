from __future__ import annotations

import math

import pandas as pd

from .regressions import ols_hc3, result_row


def run_stock_return_models(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y_cols = ["return_0_p1", "return_0_p3", "return_m1_p1", "return_m1_p3"]
    specs = [
        ("guidance_financial_sentiment", ["guidance_z_sentiment", "action_nearby_core"]),
        ("macro_financial_sentiment", ["macro_z_sentiment", "action_nearby_core"]),
        ("policy_stance", ["guidance_z_policy_stance", "action_nearby_core"]),
        ("unexpected_tone", ["guidance_unexpected_tone", "action_nearby_core"]),
    ]
    for y in y_cols:
        for name, xs in specs:
            if y not in panel or len(panel[[y, *xs]].dropna()) < len(xs) + 5:
                rows.append({"model": name, "dependent": y, "target": xs[0], "n": 0, "beta": math.nan, "se_hc3": math.nan, "p_value": math.nan, "r2": math.nan})
                continue
            result = ols_hc3(panel, y, xs)
            rows.append(result_row(result, xs[0], name))
    return pd.DataFrame(rows)
