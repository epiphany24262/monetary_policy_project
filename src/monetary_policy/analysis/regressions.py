from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


def ols_hc3(df: pd.DataFrame, y: str, x_cols: list[str]) -> dict:
    data = df[[y, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna()
    yv = data[y].astype(float)
    xv = sm.add_constant(data[x_cols].astype(float), has_constant="add")
    model = sm.OLS(yv, xv).fit(cov_type="HC3")
    return {
        "n": int(model.nobs),
        "r2": float(model.rsquared),
        "dependent": y,
        "x_cols": x_cols,
        "params": {k: float(v) for k, v in model.params.items()},
        "bse_hc3": {k: float(v) for k, v in model.bse.items()},
        "pvalues": {k: float(v) for k, v in model.pvalues.items()},
        "conf_int_95": {idx: [float(vals[0]), float(vals[1])] for idx, vals in model.conf_int().iterrows()},
        "cov_hc3": {
            str(r): {str(c): float(model.cov_params().loc[r, c]) for c in model.cov_params().columns}
            for r in model.cov_params().index
        },
        "condition_number": float(np.linalg.cond(xv.to_numpy())),
    }


def bootstrap_ci(df: pd.DataFrame, y: str, x_cols: list[str], target: str, n_boot: int = 200, seed: int = 2026) -> list[float]:
    data = df[[y, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if len(data) < 8:
        return [math.nan, math.nan]
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        sample = data.iloc[rng.integers(0, len(data), len(data))]
        try:
            vals.append(ols_hc3(sample, y, x_cols)["params"][target])
        except Exception:
            continue
    return [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def permutation_pvalue(df: pd.DataFrame, y: str, x_cols: list[str], target: str, n_perm: int = 200, seed: int = 2026) -> float:
    data = df[[y, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if len(data) < 8:
        return math.nan
    observed = abs(ols_hc3(data, y, x_cols)["params"][target])
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perm):
        perm = data.copy()
        perm[target] = rng.permutation(perm[target].to_numpy())
        stat = abs(ols_hc3(perm, y, x_cols)["params"][target])
        if stat >= observed:
            count += 1
    return float((count + 1) / (n_perm + 1))


def total_effect(result: dict, base: str, interaction: str) -> dict:
    beta = result["params"][base] + result["params"][interaction]
    cov = result["cov_hc3"]
    var = cov[base][base] + cov[interaction][interaction] + 2 * cov[base][interaction]
    se = float(np.sqrt(max(var, 0.0)))
    z = beta / se if se else np.nan
    p = float(2 * (1 - stats.norm.cdf(abs(z)))) if np.isfinite(z) else np.nan
    ci = [float(beta - 1.96 * se), float(beta + 1.96 * se)] if np.isfinite(se) else [np.nan, np.nan]
    return {"estimate": float(beta), "se_hc3": se, "p_value": p, "conf_int_95": ci}


def bootstrap_total_ci(
    df: pd.DataFrame,
    y: str,
    x_cols: list[str],
    base: str,
    interaction: str,
    n_boot: int = 200,
    seed: int = 2026,
) -> list[float]:
    data = df[[y, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if len(data) < len(x_cols) + 5:
        return [math.nan, math.nan]
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        sample = data.iloc[rng.integers(0, len(data), len(data))]
        try:
            result = ols_hc3(sample, y, x_cols)
            vals.append(result["params"][base] + result["params"][interaction])
        except Exception:
            continue
    return [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def permutation_interaction_pvalue(
    df: pd.DataFrame,
    y: str,
    x_cols: list[str],
    interaction: str,
    n_perm: int = 200,
    seed: int = 2026,
) -> float:
    data = df[[y, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if len(data) < len(x_cols) + 5:
        return math.nan
    observed = abs(ols_hc3(data, y, x_cols)["params"][interaction])
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perm):
        perm = data.copy()
        perm[interaction] = rng.permutation(perm[interaction].to_numpy())
        stat = abs(ols_hc3(perm, y, x_cols)["params"][interaction])
        if stat >= observed:
            count += 1
    return float((count + 1) / (n_perm + 1))


def vif_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    data = df[cols].replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if data.empty:
        return pd.DataFrame(columns=["variable", "vif"])
    x = sm.add_constant(data, has_constant="add")
    rows = []
    for i, col in enumerate(x.columns):
        if col == "const":
            continue
        rows.append({"variable": col, "vif": float(variance_inflation_factor(x.to_numpy(), i))})
    return pd.DataFrame(rows)


def result_row(result: dict, target: str, model_name: str) -> dict:
    beta = result["params"].get(target, math.nan)
    return {
        "model": model_name,
        "dependent": result["dependent"],
        "target": target,
        "n": result["n"],
        "beta": beta,
        "se_hc3": result["bse_hc3"].get(target, math.nan),
        "p_value": result["pvalues"].get(target, math.nan),
        "r2": result["r2"],
        "effect_percent_if_log_y": (math.exp(beta) - 1) * 100 if np.isfinite(beta) else math.nan,
    }
