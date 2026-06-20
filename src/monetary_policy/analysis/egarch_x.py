"""Custom Student-t EGARCH-X with exogenous variance regressors.

Implements the variance equation:

    log σ²_t = ω + α(|z_{t-1}| - E|z|) + γ z_{t-1} + β log σ²_{t-1}
              + δ·ReportDay_t + λ·NoveltyEvent_t + ρ·PolicyAction_t

Uses scipy.optimize for MLE with Student-t log-likelihood.
Normal distribution provided as sensitivity check only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy import stats as scipy_stats


def _student_t_loglik(params, returns, X_exog):
    """Negative log-likelihood for AR(1) + EGARCH-X with Student-t errors."""
    n = len(returns)
    mu_c, ar1, omega, alpha, gamma, beta, *exog_coeffs = params
    nu = params[-1]  # degrees of freedom
    exog_coeffs = exog_coeffs[: X_exog.shape[1]]

    sigma2 = np.zeros(n)
    z = np.zeros(n)
    # Initial variance
    sigma2[0] = np.var(returns) * 0.5
    z[0] = 0.0

    E_abs_z = math.sqrt((nu - 2) / math.pi) * math.exp(
        gammaln((nu - 1) / 2) - gammaln(nu / 2)
    ) if nu > 2 else math.sqrt(2 / math.pi)

    for t in range(1, n):
        z[t - 1] = (returns[t - 1] - mu_c - ar1 * returns[t - 2]) / math.sqrt(max(sigma2[t - 1], 1e-12)) if t >= 2 else 0.0
        exog_term = np.dot(X_exog[t], exog_coeffs)
        log_sigma2 = (
            omega
            + alpha * (abs(z[t - 1]) - E_abs_z)
            + gamma * z[t - 1]
            + beta * math.log(max(sigma2[t - 1], 1e-12))
            + exog_term
        )
        sigma2[t] = math.exp(min(log_sigma2, 20))  # clamp

    z[-1] = (returns[-1] - mu_c - ar1 * returns[-2]) / math.sqrt(max(sigma2[-1], 1e-12)) if n >= 2 else 0.0

    if nu <= 2:
        return 1e15

    ll = (
        gammaln((nu + 1) / 2)
        - gammaln(nu / 2)
        - 0.5 * math.log(math.pi * (nu - 2))
        - 0.5 * np.log(np.maximum(sigma2, 1e-12))
        - ((nu + 1) / 2) * np.log(1 + np.array(z) ** 2 / (nu - 2))
    )
    return -np.sum(ll)


def _normal_loglik(params, returns, X_exog):
    """Negative log-likelihood for AR(1) + EGARCH-X with Normal errors."""
    n = len(returns)
    mu_c, ar1, omega, alpha, gamma, beta, *exog_coeffs = params
    exog_coeffs = exog_coeffs[: X_exog.shape[1]]

    sigma2 = np.zeros(n)
    sigma2[0] = np.var(returns) * 0.5

    for t in range(1, n):
        z_prev = (returns[t - 1] - mu_c - ar1 * returns[t - 2]) / math.sqrt(max(sigma2[t - 1], 1e-12)) if t >= 2 else 0.0
        exog_term = np.dot(X_exog[t], exog_coeffs)
        log_sigma2 = (
            omega
            + alpha * (abs(z_prev) - math.sqrt(2 / math.pi))
            + gamma * z_prev
            + beta * math.log(max(sigma2[t - 1], 1e-12))
            + exog_term
        )
        sigma2[t] = math.exp(min(log_sigma2, 20))

    z = returns / np.sqrt(np.maximum(sigma2, 1e-12))
    ll = -0.5 * np.log(2 * math.pi) - 0.5 * np.log(np.maximum(sigma2, 1e-12)) - 0.5 * z**2
    return -np.sum(ll)


def _fit_egarch_x(returns, X_exog, dist="student_t", n_restarts=3):
    """Fit EGARCH-X with multiple starting values."""
    n_exog = X_exog.shape[1]
    n = len(returns)

    best_result = None
    best_ll = np.inf

    for restart in range(n_restarts):
        rng = np.random.default_rng(2026 + restart)
        init = [
            0.0,                     # mu_c
            0.05 + rng.uniform(-0.03, 0.03),  # ar1
            -0.5 + rng.uniform(-0.3, 0.3),    # omega
            0.15 + rng.uniform(-0.05, 0.05),  # alpha
            0.0 + rng.uniform(-0.05, 0.05),   # gamma
            0.9 + rng.uniform(-0.05, 0.05),   # beta
        ] + [0.0] * n_exog + [6.0 if dist == "student_t" else 0]  # exog coeffs + nu

        if dist == "normal":
            init = init[:-1]  # no nu param

        try:
            loglik_fn = _student_t_loglik if dist == "student_t" else _normal_loglik
            bounds = [
                (-0.5, 0.5), (-0.3, 0.3),      # mu_c, ar1
                (-3, 1),                         # omega
                (-0.5, 0.8),                     # alpha
                (-0.5, 0.5),                     # gamma
                (0.3, 0.999),                    # beta
            ] + [(-2, 2)] * n_exog
            if dist == "student_t":
                bounds.append((2.5, 30))  # nu

            result = minimize(
                loglik_fn, init, args=(returns, X_exog),
                method="L-BFGS-B", bounds=bounds,
                options={"maxiter": 5000, "ftol": 1e-10},
            )
            if result.fun < best_ll:
                best_ll = result.fun
                best_result = result
        except Exception:
            continue

    if best_result is None:
        return {"status": "failed", "error": "All restarts failed"}

    params = best_result.x
    n_params = 6 + n_exog + (1 if dist == "student_t" else 0)
    return {
        "status": "ok",
        "converged": bool(best_result.success),
        "loglik": float(-best_result.fun),
        "aic": float(2 * n_params - 2 * (-best_result.fun)),
        "bic": float(n_params * math.log(n) - 2 * (-best_result.fun)),
        "nobs": int(n),
        "distribution": dist,
        "params": {
            "mu_c": float(params[0]),
            "ar1": float(params[1]),
            "omega": float(params[2]),
            "alpha": float(params[3]),
            "gamma": float(params[4]),
            "beta": float(params[5]),
        },
        "exog_params": {f"exog_{i}": float(params[6 + i]) for i in range(n_exog)},
        "nu": float(params[-1]) if dist == "student_t" else None,
    }


def run_egarch_x(
    returns: pd.Series,
    report_day: pd.Series,
    novelty_event: pd.Series,
    policy_action: pd.Series | None = None,
    dist: str = "student_t",
) -> dict:
    """Fit Student-t EGARCH-X on daily returns.

    Parameters
    ----------
    returns : daily simple returns (decimal, not percent)
    report_day : 1 on report event days (D0), 0 otherwise
    novelty_event : guidance novelty on event days, 0 on non-event days
    policy_action : policy action indicator (optional)
    dist : 'student_t' or 'normal'
    """
    data = pd.DataFrame({
        "ret": returns.astype(float),
        "report_day": report_day.astype(float).fillna(0),
        "novelty": novelty_event.astype(float).fillna(0),
    })
    if policy_action is not None:
        data["policy_action"] = policy_action.astype(float).fillna(0)
    else:
        data["policy_action"] = 0.0

    data = data.dropna(subset=["ret"])
    ret_arr = data["ret"].to_numpy()
    X = data[["report_day", "novelty", "policy_action"]].to_numpy()

    result = _fit_egarch_x(ret_arr, X, dist=dist, n_restarts=3)

    # Post-estimation diagnostics
    if result["status"] == "ok" and result["converged"]:
        # Residual analysis
        sigma2 = np.zeros(len(ret_arr))
        sigma2[0] = np.var(ret_arr) * 0.5
        params = result["params"]
        exog_p = [result["exog_params"].get(f"exog_{i}", 0) for i in range(3)]
        nu = result.get("nu", 5)
        e_abs_z = math.sqrt((nu - 2) / math.pi) * math.exp(
            gammaln((nu - 1) / 2) - gammaln(nu / 2)
        ) if dist == "student_t" and nu and nu > 2 else math.sqrt(2 / math.pi)

        for t in range(1, len(ret_arr)):
            z_prev = (ret_arr[t - 1] - params["mu_c"] - params["ar1"] * ret_arr[t - 2]) / math.sqrt(max(sigma2[t - 1], 1e-12)) if t >= 2 else 0.0
            exog_term = np.dot(X[t], exog_p)
            log_s2 = (
                params["omega"]
                + params["alpha"] * (abs(z_prev) - e_abs_z)
                + params["gamma"] * z_prev
                + params["beta"] * math.log(max(sigma2[t - 1], 1e-12))
                + exog_term
            )
            sigma2[t] = math.exp(min(log_s2, 20))

        std_resid = ret_arr / np.sqrt(np.maximum(sigma2, 1e-12))
        result["diagnostics"] = {
            "std_residuals_mean": float(np.mean(std_resid)),
            "std_residuals_std": float(np.std(std_resid)),
            "condition_vol_mean": float(np.mean(np.sqrt(sigma2))),
        }

    return result


def permutation_test_novelty(
    returns: pd.Series,
    report_day: pd.Series,
    novelty_event: pd.Series,
    policy_action: pd.Series | None = None,
    n_perm: int = 200,
    seed: int = 2026,
) -> float:
    """Permutation test for novelty coefficient in EGARCH-X."""
    rng = np.random.default_rng(seed)
    base = run_egarch_x(returns, report_day, novelty_event, policy_action=policy_action)
    if base["status"] != "ok":
        return float("nan")
    observed = abs(base["exog_params"].get("exog_1", 0))
    count = 0
    for _ in range(n_perm):
        perm_novelty = rng.permutation(novelty_event.to_numpy())
        perm_result = run_egarch_x(
            returns,
            report_day,
            pd.Series(perm_novelty, index=novelty_event.index),
            policy_action=policy_action,
        )
        if perm_result["status"] != "ok":
            continue
        if abs(perm_result["exog_params"].get("exog_1", 0)) >= observed:
            count += 1
    return float((count + 1) / (n_perm + 1))


def run_egarch_x_sensitivity(
    returns: pd.Series,
    report_days: dict[str, pd.Series],
    novelty_event: pd.Series,
    policy_action: pd.Series | None = None,
    dist: str = "student_t",
) -> pd.DataFrame:
    """Sensitivity: D0, D0+D1, D+1 window variants."""
    rows = []
    for label, rd in report_days.items():
        result = run_egarch_x(returns, rd, novelty_event, policy_action=policy_action, dist=dist)
        rows.append({
            "date_window": label,
            "status": result["status"],
            "converged": result.get("converged"),
            "aic": result.get("aic"),
            "novelty_coef": result["exog_params"].get("exog_1") if result.get("exog_params") else None,
            "report_day_coef": result["exog_params"].get("exog_0") if result.get("exog_params") else None,
            "distribution": dist,
        })
    return pd.DataFrame(rows)


def write_egarch_x_results(path: Path, result: dict, sensitivity: pd.DataFrame) -> None:
    """Write EGARCH-X results to JSON."""
    out = {
        "main_model": {k: v for k, v in result.items() if k != "diagnostics"},
        "diagnostics": result.get("diagnostics"),
        "sensitivity": sensitivity.to_dict(orient="records"),
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
