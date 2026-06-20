from __future__ import annotations

import json

import pandas as pd

from ..paths import ROOT
from .regressions import (
    bootstrap_ci,
    bootstrap_total_ci,
    ols_hc3,
    permutation_interaction_pvalue,
    permutation_pvalue,
    result_row,
    total_effect,
)


def run_yield_curve_models(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    x = ["guidance_unexpected_tone", "action_nearby_core", "post_2019", "guidance_unexpected_tone_x_post_2019"]
    y_cols = ["delta_slope_bp_0_3", "delta_level_bp_0_3", "delta_curvature_bp_0_3"]
    for y in y_cols:
        result = ols_hc3(panel, y, x)
        row = result_row(result, "guidance_unexpected_tone", "main_yield_curve" if y == "delta_slope_bp_0_3" else "secondary_yield_curve")
        row["post_2019_interaction_beta"] = result["params"].get("guidance_unexpected_tone_x_post_2019")
        row["post_2019_total_effect"] = total_effect(result, "guidance_unexpected_tone", "guidance_unexpected_tone_x_post_2019")["estimate"]
        row["post_2019_total_p_value"] = total_effect(result, "guidance_unexpected_tone", "guidance_unexpected_tone_x_post_2019")["p_value"]
        row["bootstrap_ci_95_base"] = bootstrap_ci(panel, y, x, "guidance_unexpected_tone")
        row["bootstrap_ci_95_total"] = bootstrap_total_ci(panel, y, x, "guidance_unexpected_tone", "guidance_unexpected_tone_x_post_2019")
        row["permutation_p_base"] = permutation_pvalue(panel, y, x, "guidance_unexpected_tone")
        row["permutation_p_interaction"] = permutation_interaction_pvalue(panel, y, x, "guidance_unexpected_tone_x_post_2019")
        rows.append(row)
    legacy_path = ROOT / "output/results/legacy_primary_result.json"
    if not legacy_path.exists():
        legacy_path = ROOT / "output/results/primary/PRIMARY_RESULT_LOCK.json"
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    rows.append(
        {
            "model": "legacy_1y_m1_p3",
            "dependent": "delta_yield_1y_bp_m1_p3",
            "target": "guidance_tone_change",
            "n": legacy["n"],
            "beta": legacy["params"]["guidance_tone_change"],
            "se_hc3": legacy["bse_hc3"]["guidance_tone_change"],
            "p_value": legacy["pvalues"]["guidance_tone_change"],
            "r2": legacy["r2"],
            "effect_percent_if_log_y": pd.NA,
        }
    )
    return pd.DataFrame(rows)
