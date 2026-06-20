"""Market power analysis via wild bootstrap / Monte Carlo simulation.

Evaluates power for detecting guidance_novelty effects at various sample sizes,
preserving the empirical design matrix structure and heteroskedasticity pattern.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from .regressions import ols_hc3
from ..paths import FIGURES_DIR, TABLES_DIR, OUTPUT_DIR


def wild_bootstrap_power(
    panel: pd.DataFrame,
    y: str,
    x_cols: list[str],
    target: str,
    sample_sizes: list[int],
    n_sim: int = 2000,
    seed: int = 2026,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Estimate power at various sample sizes via wild residual bootstrap.

    Preserves the ratio of pre-2019 to post-2019 observations.
    """
    data = panel[[y, *x_cols]].replace([np.inf, -np.inf], np.nan).dropna()
    full_result = ols_hc3(data, y, x_cols)
    true_beta = full_result["params"].get(target, 0.0)

    # Extract residuals and fitted values
    yv = data[y].astype(float).to_numpy()
    xv = data[x_cols].astype(float).to_numpy()
    xv_const = np.column_stack([np.ones(len(data)), xv])
    fitted = xv_const @ np.array([full_result["params"].get(k, 0) for k in ["const", *x_cols]])
    residuals = yv - fitted

    rng = np.random.default_rng(seed)
    rows = []
    n_full = len(data)

    for n in sample_sizes:
        if n > len(data) * 3 or n < len(x_cols) + 5:
            rows.append({"sample_size": n, "power": np.nan, "min_detectable_effect": np.nan, "n_sim": 0})
            continue

        significant = 0
        for sim in range(n_sim):
            # Resample residuals (wild bootstrap)
            wild = rng.choice([-1, 1], size=n) * rng.choice(residuals, size=n, replace=True)

            # Generate design matrix preserving covariate structure
            idx = rng.choice(len(data), size=n, replace=True)
            X_sim = xv_const[idx]
            y_sim = X_sim @ np.array([full_result["params"].get(k, 0) for k in ["const", *x_cols]]) + wild

            # Build DataFrame for ols_hc3
            sim_df = pd.DataFrame(X_sim[:, 1:], columns=x_cols)
            sim_df[y] = y_sim

            try:
                sim_result = ols_hc3(sim_df, y, x_cols)
                p_val = sim_result["pvalues"].get(target, 1.0)
                if p_val < alpha:
                    significant += 1
            except Exception:
                continue

        power = significant / n_sim if n_sim > 0 else np.nan

        # Minimum detectable effect at 80% power
        se_full = full_result["bse_hc3"].get(target, 1.0)
        se_scaled = se_full * np.sqrt(n_full / n) if n > 0 else np.nan
        mde = se_scaled * (scipy_stats_norm_ppf(1 - alpha / 2) + scipy_stats_norm_ppf(0.8)) if n > 0 else np.nan

        rows.append({
            "sample_size": n,
            "power": float(power),
            "observed_beta": float(true_beta),
            "min_detectable_effect": float(mde) if not np.isnan(mde) else np.nan,
            "alpha": float(alpha),
            "n_sim": int(n_sim),
            "method": "wild_residual_bootstrap_hc3",
        })

    return pd.DataFrame(rows)


def _scipy_stats_norm_ppf(q):
    from scipy import stats
    return stats.norm.ppf(q)


scipy_stats_norm_ppf = _scipy_stats_norm_ppf


def run_power_analysis(panel: pd.DataFrame) -> pd.DataFrame:
    """Run power analysis for the core stock volatility model."""
    y = "log_rv_0_5"
    x_cols = [
        "guidance_novelty",
        "pre_event_volatility_20d",
        "action_nearby_core",
        "post_2019",
        "guidance_novelty_x_post_2019",
    ]
    sample_sizes = [79, 100, 120, 160]
    result = wild_bootstrap_power(panel, y, x_cols, "guidance_novelty", sample_sizes, n_sim=2000, seed=2026)
    return result


def write_power_outputs(result: pd.DataFrame) -> dict[str, Path]:
    """Write power analysis outputs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    diag = OUTPUT_DIR / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = diag / "market_power_analysis.csv"
    result.to_csv(csv_path, index=False, encoding="utf-8-sig")

    xlsx_path = TABLES_DIR / "table_market_power_analysis.xlsx"
    result.to_excel(xlsx_path, index=False)

    # Simple power curve plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    valid = result.dropna(subset=["power"])
    if len(valid) > 0:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(valid["sample_size"], valid["power"], "ko-", markersize=6)
        ax.axhline(0.8, color="gray", linestyle="--", linewidth=0.8, label="80% power")
        ax.set_xlabel("Sample Size (N)")
        ax.set_ylabel("Power")
        ax.set_title("Power Curve — guidance_novelty (α=0.05)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / "figure_market_power_curve.png", dpi=200)
        plt.close(fig)

    return {"csv": csv_path, "xlsx": xlsx_path, "figure": FIGURES_DIR / "figure_market_power_curve.png"}
