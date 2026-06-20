from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from ..config import load_config
from ..data.market_prices import load_stock_prices
from ..events.event_calendar import load_event_calendar
from .regressions import (
    bootstrap_ci,
    bootstrap_total_ci,
    ols_hc3,
    permutation_interaction_pvalue,
    permutation_pvalue,
    result_row,
    total_effect,
    vif_table,
)


def _subsample(df: pd.DataFrame, name: str) -> pd.DataFrame:
    dt = pd.to_datetime(df["equity_event_date"])
    if name == "full":
        return df
    if name == "pre_2019":
        return df[dt <= pd.Timestamp("2018-12-31")]
    if name == "post_2019":
        return df[dt >= pd.Timestamp("2019-01-01")]
    if name == "covid":
        return df[(dt >= pd.Timestamp("2020-01-01")) & (dt <= pd.Timestamp("2022-12-31"))]
    if name == "non_covid":
        return df[(dt < pd.Timestamp("2020-01-01")) | (dt > pd.Timestamp("2022-12-31"))]
    raise KeyError(name)


def run_stock_volatility_models(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    y = "log_rv_0_5"
    x = [
        "guidance_novelty",
        "pre_event_volatility_20d",
        "action_nearby_core",
        "post_2019",
        "guidance_novelty_x_post_2019",
    ]
    rows = []
    main_result = None
    for sample in ["full", "pre_2019", "post_2019", "covid", "non_covid"]:
        data = _subsample(panel, sample)
        xs = x if sample == "full" else ["guidance_novelty", "pre_event_volatility_20d", "action_nearby_core", "centered_time_trend"]
        if len(data.dropna(subset=[y, *xs])) < len(xs) + 5:
            rows.append({"model": sample, "dependent": y, "target": "guidance_novelty", "n": len(data), "beta": math.nan, "se_hc3": math.nan, "p_value": math.nan, "r2": math.nan, "effect_percent_if_log_y": math.nan})
            continue
        result = ols_hc3(data, y, xs)
        if sample == "full":
            main_result = result
        rows.append(result_row(result, "guidance_novelty", sample))
    table = pd.DataFrame(rows)
    main = main_result or ols_hc3(panel, y, x)
    main["bootstrap_ci_95_guidance_novelty"] = bootstrap_ci(panel, y, x, "guidance_novelty")
    main["bootstrap_ci_95_post_2019_total_effect"] = bootstrap_total_ci(
        panel, y, x, "guidance_novelty", "guidance_novelty_x_post_2019"
    )
    main["permutation_pvalue_guidance_novelty"] = permutation_pvalue(panel, y, x, "guidance_novelty")
    main["permutation_pvalue_interaction"] = permutation_interaction_pvalue(panel, y, x, "guidance_novelty_x_post_2019")
    main["post_2019_total_effect"] = total_effect(main, "guidance_novelty", "guidance_novelty_x_post_2019")
    main["vif"] = vif_table(panel, x).to_dict(orient="records")
    beta = main["params"]["guidance_novelty"]
    main["economic_effect"] = {
        "one_unit_guidance_novelty_log_rv_beta": beta,
        "one_unit_guidance_novelty_percent_change_in_rv": (np.exp(beta) - 1) * 100,
    }
    return table, main, _legacy_arx_mean_diagnostic_not_run()


def _legacy_arx_mean_diagnostic_not_run() -> dict:
    return {
        "status": "not_run",
        "method": "legacy_arx_mean_equation_diagnostic_disabled",
        "note": "The old arch_model mean='ARX' diagnostic is not part of the formal pipeline. Formal daily Student-t EGARCH-X variance-equation results are produced by analysis/egarch_x.py.",
    }


def run_legacy_arx_mean_diagnostic(panel: pd.DataFrame) -> dict:
    """Legacy diagnostic retained for audit only; not called by the formal pipeline."""
    from arch import arch_model

    stock = load_stock_prices().copy()
    events = load_event_calendar()[["event_id", "equity_event_date"]].merge(
        panel[["event_id", "guidance_novelty"]], on="event_id", how="left"
    )
    stock["event_similarity"] = 0.0
    mapping = {pd.to_datetime(row["equity_event_date"]).date(): row["guidance_novelty"] for _, row in events.dropna().iterrows()}
    stock["event_guidance_novelty"] = stock["date"].dt.date.map(mapping).fillna(0.0)
    data = stock[["simple_return", "event_guidance_novelty"]].dropna().copy()
    try:
        model = arch_model(data["simple_return"] * 100, x=data[["event_guidance_novelty"]], mean="ARX", lags=1, vol="EGARCH", p=1, o=1, q=1, dist="normal")
        result = model.fit(disp="off", show_warning=False)
        return {
            "status": "ok",
            "method": "legacy_arx_mean_equation_diagnostic_not_formal_daily_egarch_x",
            "converged": bool(result.convergence_flag == 0),
            "nobs": int(result.nobs),
            "aic": float(result.aic),
            "params": {k: float(v) for k, v in result.params.items()},
            "interpretation_warning": "This legacy diagnostic places the text variable in an ARX mean equation only. It is not the formal Student-t EGARCH-X robustness model and is not used for paper inference.",
            "note": "The event-level realized volatility regression remains the core volatility test; the formal daily EGARCH-X result is produced by analysis/egarch_x.py.",
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "note": "Realized volatility model remains the core specification."}


def write_egarch(path, diagnostic: dict) -> None:
    path.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
