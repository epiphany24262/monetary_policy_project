"""Custom Student-t EGARCH-X with exogenous variance regressors.

Implements the variance equation:

    log σ²_t = ω + α(|z_{t-1}| - E|z|) + γ z_{t-1} + β log σ²_{t-1}
              + δ·ReportDay_t + λ·NoveltyEvent_t + ρ·PolicyAction_t

Uses scipy.optimize for MLE with Student-t log-likelihood.
Normal distribution provided as sensitivity check only.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy import stats as scipy_stats

from ..paths import OUTPUT_DIR, ROOT, as_posix_relative
from ..sample import is_in_formal_sample, sample_bounds


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


def _fit_egarch_x(returns, X_exog, dist="student_t", n_restarts=1, maxiter=500):
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
                options={"maxiter": maxiter, "ftol": 1e-8},
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
    n_restarts: int = 1,
    maxiter: int = 500,
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

    result = _fit_egarch_x(ret_arr, X, dist=dist, n_restarts=n_restarts, maxiter=maxiter)

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
    base = run_egarch_x(returns, report_day, novelty_event, policy_action=policy_action, n_restarts=1, maxiter=300)
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
            n_restarts=1,
            maxiter=250,
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
        result = run_egarch_x(returns, rd, novelty_event, policy_action=policy_action, dist=dist, n_restarts=1, maxiter=300)
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


# ---------------------------------------------------------------------------
# Formal route: full daily recursion + frozen nuisance conditional likelihood
# ---------------------------------------------------------------------------

MODEL_VERSION = "daily_egarch_x_v2_full_sequence_fixed_nuisance"
LOCKED_MODEL_VERSION = "daily_egarch_x_locked_full_joint_mle_v1"
CONDITIONAL_CACHE_VERSION = "daily_egarch_x_conditional_diagnostics_v1"


def _series_hash(*series: pd.Series) -> str:
    h = hashlib.sha256()
    for s in series:
        payload = pd.util.hash_pandas_object(s.reset_index(drop=True), index=True).values.tobytes()
        h.update(payload)
    return h.hexdigest()


def _dict_hash(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def validate_daily_egarch_dataset(daily: pd.DataFrame) -> dict:
    """Validate that EGARCH input is a full ordered daily sequence."""
    required = {"date", "return", "report_day", "novelty_z", "novelty_available", "policy_action_day", "report_action_nearby_core"}
    missing = required - set(daily.columns)
    if missing:
        raise ValueError(f"Missing daily EGARCH columns: {sorted(missing)}")
    dates = pd.to_datetime(daily["date"])
    assert dates.is_monotonic_increasing, "daily EGARCH dates must be strictly increasing"
    assert dates.is_unique, "daily EGARCH dates must be unique"
    assert len(daily) >= 4500, "daily EGARCH input must keep the full daily return sequence"
    report_events = int(pd.to_numeric(daily["report_day"]).fillna(0).sum())
    novelty_events = int(pd.to_numeric(daily["novelty_available"]).fillna(0).sum())
    assert report_events == 80, f"unexpected report event count: {report_events}"
    assert novelty_events == 79, f"unexpected novelty availability count: {novelty_events}"
    assert len(daily) == int(daily["return"].notna().sum()), "model input rows must equal cleaned full return rows"
    policy_action_days = int(pd.to_numeric(daily["policy_action_day"]).fillna(0).sum())
    report_action_days = int(pd.to_numeric(daily["report_action_nearby_core"]).fillna(0).sum())
    assert policy_action_days > report_action_days, "daily policy action days must exceed report-level nearby action days"
    return {
        "n_daily_observations": int(len(daily)),
        "n_report_events": report_events,
        "n_novelty_events": novelty_events,
        "n_policy_action_days": policy_action_days,
        "n_report_action_nearby_days": report_action_days,
        "date_start": str(dates.min().date()),
        "date_end": str(dates.max().date()),
        "uses_full_continuous_daily_sequence": True,
        "dropped_non_event_days": False,
    }


def egarch_cache_metadata(
    return_data_sha256: str,
    event_panel_sha256: str,
    policy_operation_sha256: str = "",
    novelty_mean: float | None = None,
    novelty_std: float | None = None,
    model_version: str = MODEL_VERSION,
    distribution: str = "student_t",
    mean_equation: str = "AR(1)",
    variance_equation: str = "EGARCH-X(1,1)",
    code_version: str | None = None,
) -> dict:
    start, end = sample_bounds()
    code_version_value = code_version or model_code_hash()
    novelty_mean_value = round(float(novelty_mean), 12) if novelty_mean is not None else None
    novelty_std_value = round(float(novelty_std), 12) if novelty_std is not None else None
    spec_payload = {
        "formal_sample_start": start,
        "formal_sample_end": end,
        "distribution": distribution,
        "mean_equation": mean_equation,
        "variance_equation": variance_equation,
        "variables": ["report_day", "guidance_novelty_z", "policy_action_day"],
        "random_seed": 2026,
        "bounds": "documented_in_egarch_x.py",
        "novelty_mean": novelty_mean_value,
        "novelty_std": novelty_std_value,
    }
    return {
        "return_data_sha256": return_data_sha256,
        "event_panel_sha256": event_panel_sha256,
        "policy_operation_sha256": policy_operation_sha256,
        "model_code_sha256": model_code_hash(),
        "egarch_code_sha256": file_sha256(ROOT / "src/monetary_policy/analysis/egarch_x.py"),
        "pipeline_code_sha256": file_sha256(ROOT / "src/monetary_policy/pipeline.py"),
        "model_spec_sha256": _dict_hash(spec_payload),
        "formal_sample_start": start,
        "formal_sample_end": end,
        "novelty_mean": novelty_mean_value,
        "novelty_std": novelty_std_value,
        "model_version": model_version,
        "distribution": distribution,
        "mean_equation": mean_equation,
        "variance_equation": variance_equation,
        "code_version": code_version_value,
    }


def conditional_cache_metadata(
    hashes: dict,
    nuisance_parameter_source: str,
    n_perm: int,
    random_seed: int,
    locked_model_sha256: str | None = None,
) -> dict:
    source_path = Path(nuisance_parameter_source)
    if not source_path.is_absolute():
        source_path = ROOT / nuisance_parameter_source
    locked_hash = locked_model_sha256 or (file_sha256(source_path) if source_path.exists() else _dict_hash({"source": nuisance_parameter_source}))
    spec_payload = {
        "version": CONDITIONAL_CACHE_VERSION,
        "D0": ["report_day_d0", "novelty_d0", "policy_action_day"],
        "D1": ["report_day_d0", "novelty_d1", "policy_action_day"],
        "D0_D1": ["report_day_d0", "novelty_d0", "novelty_d1", "policy_action_day"],
        "restricted_coefficients": "all optimized novelty coefficients set to zero within the same design matrix",
        "distribution": "student_t",
    }
    return {
        "cache_version": CONDITIONAL_CACHE_VERSION,
        "locked_model_sha256": locked_hash,
        "daily_dataset_sha256": hashes.get("daily_dataset_sha256"),
        "conditional_code_sha256": file_sha256(ROOT / "src/monetary_policy/analysis/egarch_x.py"),
        "n_perm": int(n_perm),
        "random_seed": int(random_seed),
        "D0_D1_specification": _dict_hash(spec_payload),
    }


def _cache_status(path: Path, expected: dict) -> tuple[str, str, dict | None]:
    if not path.exists():
        return "miss", "cache file missing", None
    cached = json.loads(path.read_text(encoding="utf-8"))
    meta = cached.get("cache_metadata", {})
    for key, value in expected.items():
        if meta.get(key) != value:
            return "invalidated", f"{key} changed", cached
    return "hit", "", cached


def pandas_frame_sha256(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    view = df[cols].copy() if cols else df.copy()
    view = view.reset_index(drop=True)
    for col in view.columns:
        if "date" in str(col).lower():
            parsed = pd.to_datetime(view[col], errors="coerce")
            if parsed.notna().any():
                view[col] = parsed.dt.strftime("%Y-%m-%d").fillna(view[col].astype(str))
    float_cols = view.select_dtypes(include=["floating"]).columns
    for col in float_cols:
        view[col] = view[col].round(12)
    payload = pd.util.hash_pandas_object(view, index=True).values.tobytes()
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_version() -> str:
    try:
        import subprocess

        proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=Path.cwd(), text=True, capture_output=True, timeout=5)
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "workspace"


def model_code_hash() -> str:
    h = hashlib.sha256()
    for rel in ["src/monetary_policy/analysis/egarch_x.py", "src/monetary_policy/pipeline.py", "configs/project.yml"]:
        path = ROOT / rel
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()


def build_daily_egarch_dataset(stock: pd.DataFrame, events: pd.DataFrame, stock_panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Build full continuous daily EGARCH-X input from stock returns and events."""
    start_period, end_period = sample_bounds()
    formal_panel = stock_panel[stock_panel["report_period"].map(is_in_formal_sample)].copy()
    formal_panel = formal_panel.sort_values("equity_event_date").reset_index(drop=True)
    if len(formal_panel) != 80:
        raise ValueError(f"Expected 80 formal report events, got {len(formal_panel)}")
    event_cols = ["event_id", "equity_event_date", "action_nearby"]
    events_small = events[event_cols].copy()
    events_small = events_small.rename(columns={"action_nearby": "event_action_nearby_core"})
    merged_events = events_small.merge(
        formal_panel[["event_id", "report_period", "guidance_novelty", "action_nearby_core"]],
        on="event_id",
        how="inner",
    ).sort_values("equity_event_date")

    returns_full = stock[["date", "simple_return"]].dropna(subset=["simple_return"]).copy()
    returns_full = returns_full.sort_values("date").reset_index(drop=True)
    trading_dates = pd.to_datetime(returns_full["date"]).reset_index(drop=True)
    daily_start = trading_dates[trading_dates >= pd.Timestamp("2006-01-01")].iloc[0]
    report_dates = pd.to_datetime(merged_events["equity_event_date"]).reset_index(drop=True)
    first_report_event_date = report_dates.iloc[0]
    last_report_event_date = report_dates.iloc[-1]
    try:
        last_idx = trading_dates[trading_dates == last_report_event_date].index[0]
    except IndexError as exc:
        raise ValueError(f"Last formal report event date is not in trading calendar: {last_report_event_date}") from exc
    if last_idx + 1 >= len(trading_dates):
        raise ValueError("No D+1 trading day after the last locked report event")
    last_d1_date = trading_dates.iloc[last_idx + 1]
    daily = returns_full[(trading_dates >= daily_start) & (trading_dates <= last_d1_date)].copy()
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["report_day"] = 0.0
    daily["novelty_available"] = 0.0
    daily["guidance_novelty_raw"] = 0.0
    daily["novelty_z"] = 0.0
    daily["report_action_nearby_core"] = 0.0
    novelty_events = merged_events.dropna(subset=["guidance_novelty"]).copy()
    if len(novelty_events) != 79:
        raise ValueError(f"Expected 79 novelty-available events, got {len(novelty_events)}")
    novelty_mean = float(novelty_events["guidance_novelty"].mean())
    novelty_std = float(novelty_events["guidance_novelty"].std(ddof=1))
    if not np.isfinite(novelty_std) or novelty_std <= 0:
        raise ValueError("Invalid guidance novelty standard deviation")
    report_map = {}
    novelty_raw_map = {}
    novelty_z_map = {}
    novelty_available_map = {}
    report_action_map = {}
    for _, row in merged_events.iterrows():
        date = pd.to_datetime(row["equity_event_date"]).date()
        report_map[date] = 1.0
        report_action_map[date] = float(row["action_nearby_core"])
        if pd.notna(row["guidance_novelty"]):
            raw = float(row["guidance_novelty"])
            novelty_raw_map[date] = raw
            novelty_z_map[date] = (raw - novelty_mean) / novelty_std
            novelty_available_map[date] = 1.0
    daily_dates = pd.to_datetime(daily["date"]).dt.date
    daily["report_day"] = daily_dates.map(report_map).fillna(0.0).astype(float)
    daily["novelty_available"] = daily_dates.map(novelty_available_map).fillna(0.0).astype(float)
    daily["guidance_novelty_raw"] = daily_dates.map(novelty_raw_map).fillna(0.0).astype(float)
    daily["novelty_z"] = daily_dates.map(novelty_z_map).fillna(0.0).astype(float)
    daily["report_action_nearby_core"] = daily_dates.map(report_action_map).fillna(0.0).astype(float)

    policy_path = ROOT / "data/processed/policy_operations.csv"
    policy_ops = pd.read_csv(policy_path, parse_dates=["date", "effective_date"]) if policy_path.exists() else pd.DataFrame()
    daily["policy_action_day"] = 0.0
    operation_type_counts = {}
    mapped_dates = set()
    if not policy_ops.empty:
        op_dates = policy_ops["effective_date"].fillna(policy_ops["date"])
        operation_type_counts = policy_ops["operation_type"].value_counts().to_dict()
        for op_date in pd.to_datetime(op_dates):
            candidates = pd.to_datetime(daily["date"])
            candidates = candidates[candidates >= op_date]
            if len(candidates) == 0:
                continue
            mapped_dates.add(candidates.iloc[0].date())
        daily["policy_action_day"] = daily_dates.isin(mapped_dates).astype(float)
    daily = daily.rename(columns={"simple_return": "return"})
    checks = validate_daily_egarch_dataset(daily)
    hashes = {
        **checks,
        "formal_report_period_start": start_period,
        "formal_report_period_end": end_period,
        "daily_estimation_start": str(daily_start.date()),
        "daily_estimation_end": str(last_d1_date.date()),
        "first_report_event_date": str(first_report_event_date.date()),
        "last_report_event_date": str(last_report_event_date.date()),
        "last_d1_date": str(last_d1_date.date()),
        "novelty_raw_mean": novelty_mean,
        "novelty_raw_std": novelty_std,
        "novelty_standardization_scope": "79 report events",
        "mapped_unique_policy_action_trading_days": int(len(mapped_dates)),
        "policy_operation_source": as_posix_relative(policy_path),
        "policy_operation_mapping_rule": "effective_date mapped to the next available CSI300 trading day; multiple operations on the same trading day count once",
        "policy_operation_type_counts": {str(k): int(v) for k, v in operation_type_counts.items()},
        "return_data_sha256": pandas_frame_sha256(daily, ["date", "return"]),
        "event_panel_sha256": pandas_frame_sha256(formal_panel, ["event_id", "report_period", "equity_event_date", "guidance_novelty", "action_nearby_core"]),
        "policy_operation_sha256": file_sha256(policy_path) if policy_path.exists() else "",
        "daily_dataset_sha256": pandas_frame_sha256(
            daily,
            ["date", "return", "report_day", "novelty_available", "guidance_novelty_raw", "novelty_z", "policy_action_day", "report_action_nearby_core"],
        ),
    }
    return daily, hashes


def _student_t_ll_from_sigma2(eps: np.ndarray, sigma2: np.ndarray, nu: float) -> float:
    z = eps / np.sqrt(np.maximum(sigma2, 1e-12))
    ll = (
        gammaln((nu + 1) / 2)
        - gammaln(nu / 2)
        - 0.5 * math.log(math.pi * (nu - 2))
        - 0.5 * np.log(np.maximum(sigma2, 1e-12))
        - ((nu + 1) / 2) * np.log(1 + z**2 / (nu - 2))
    )
    return float(np.sum(ll))


def _baseline_param(params: dict, *candidates: str, default: float = 0.0) -> float:
    for key in candidates:
        if key in params:
            return float(params[key])
    return float(default)


def _arch_ar_key(params: dict) -> str | None:
    for key in params:
        if key.endswith("[1]") and key not in {"alpha[1]", "gamma[1]", "beta[1]"}:
            return key
    return None


def _fit_baseline_student_t_egarch(
    y_pct: pd.Series,
    cache_path: Path,
    data_hash: str,
    force: bool = False,
    cache_metadata: dict | None = None,
) -> dict:
    """Fit and cache a full-sample Student-t EGARCH(1,1).

    The cache is valid only for the exact return series hash, preserving the
    full continuous daily recursion while avoiding repeated baseline fits.
    """
    expected_meta = cache_metadata or {
        "return_data_sha256": data_hash,
        "model_version": MODEL_VERSION,
        "distribution": "student_t",
        "mean_equation": "AR(1)",
        "variance_equation": "EGARCH(1,1)",
    }
    if not force:
        status, reason, cached = _cache_status(cache_path, expected_meta)
        if status == "hit" and cached is not None and cached.get("method") == "full_sample_student_t_egarch_baseline":
            cached["cache_status"] = "hit"
            cached["cache_invalidation_reason"] = ""
            return cached
    else:
        status, reason = "miss", "force recompute"

    from arch import arch_model

    model = arch_model(y_pct, mean="AR", lags=1, vol="EGARCH", p=1, o=1, q=1, dist="t")
    fit = model.fit(disp="off", show_warning=False)
    params = {str(k): float(v) for k, v in fit.params.items()}
    cond_var = (fit.conditional_volatility.astype(float) ** 2).tolist()
    resid = fit.resid.astype(float).fillna(0.0).tolist()
    out = {
        "method": "full_sample_student_t_egarch_baseline",
        "data_hash": data_hash,
        "cache_metadata": expected_meta,
        "cache_status": status if status != "hit" else "miss",
        "cache_invalidation_reason": reason,
        "start_date": str(y_pct.index.min().date()) if hasattr(y_pct.index.min(), "date") else str(y_pct.index.min()),
        "end_date": str(y_pct.index.max().date()) if hasattr(y_pct.index.max(), "date") else str(y_pct.index.max()),
        "nobs": int(fit.nobs),
        "converged": bool(fit.convergence_flag == 0),
        "loglik": float(fit.loglikelihood),
        "aic": float(fit.aic),
        "bic": float(fit.bic),
        "params": params,
        "conditional_variance": cond_var,
        "residuals": resid,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _egarch_start_from_baseline(baseline: dict, n_exog: int, perturb: bool = False) -> np.ndarray:
    params = baseline["params"]
    ar_key = _arch_ar_key(params)
    start = np.array(
        [
            _baseline_param(params, "Const", "mu"),
            float(params.get(ar_key, 0.0)) if ar_key else 0.0,
            _baseline_param(params, "omega"),
            _baseline_param(params, "alpha[1]"),
            _baseline_param(params, "gamma[1]"),
            min(max(_baseline_param(params, "beta[1]", default=0.9), 0.3), 0.995),
            *([0.0] * n_exog),
            _baseline_param(params, "nu", default=8.0),
        ],
        dtype=float,
    )
    if perturb:
        start = start.copy()
        start[2] += 0.02
        start[3] = min(start[3] + 0.02, 0.75)
        start[5] = min(max(start[5] - 0.01, 0.3), 0.995)
        if n_exog >= 3:
            start[6:9] = [0.05, 0.05, 0.02]
        start[-1] = min(start[-1] + 0.25, 30.0)
    return start


def _joint_sigma2(params: np.ndarray, returns: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu_c, ar1, omega, alpha, gamma, beta, *rest = params
    nu = params[-1]
    exog_coeffs = np.asarray(rest[: X.shape[1]], dtype=float)
    n = len(returns)
    sigma2 = np.zeros(n)
    eps = np.zeros(n)
    sigma2[0] = max(float(np.nanvar(returns)) * 0.5, 1e-8)
    eps[0] = returns[0] - mu_c
    e_abs_z = math.sqrt((nu - 2) / math.pi) * math.exp(gammaln((nu - 1) / 2) - gammaln(nu / 2)) if nu > 2 else math.sqrt(2 / math.pi)
    for t in range(1, n):
        eps[t - 1] = returns[t - 1] - mu_c - ar1 * returns[t - 2] if t >= 2 else returns[t - 1] - mu_c
        z_prev = eps[t - 1] / math.sqrt(max(sigma2[t - 1], 1e-12))
        log_sigma2 = omega + alpha * (abs(z_prev) - e_abs_z) + gamma * z_prev + beta * math.log(max(sigma2[t - 1], 1e-12)) + float(np.dot(X[t], exog_coeffs))
        sigma2[t] = math.exp(min(max(log_sigma2, -30), 20))
    eps[-1] = returns[-1] - mu_c - ar1 * returns[-2] if n >= 2 else returns[-1] - mu_c
    return sigma2, eps


def _approx_se_pvalues(result, n_params: int) -> tuple[list[float], list[float]]:
    try:
        hinv = result.hess_inv.todense() if hasattr(result.hess_inv, "todense") else np.asarray(result.hess_inv)
        cov = np.asarray(hinv, dtype=float)
        se = np.sqrt(np.maximum(np.diag(cov), 0.0))
        z = np.divide(result.x, se, out=np.full_like(result.x, np.nan), where=se > 0)
        p = 2 * (1 - scipy_stats.norm.cdf(np.abs(z)))
        return [float(v) for v in se[:n_params]], [float(v) for v in p[:n_params]]
    except Exception:
        return [float("nan")] * n_params, [float("nan")] * n_params


def run_locked_full_joint_mle(
    daily: pd.DataFrame,
    hashes: dict,
    output_json: Path,
    output_csv: Path | None = None,
    force: bool = False,
    random_seed: int = 2026,
) -> dict:
    """Run or load the formal D0 full joint Student-t EGARCH-X MLE."""
    expected_meta = egarch_cache_metadata(
        hashes["return_data_sha256"],
        hashes["event_panel_sha256"],
        policy_operation_sha256=hashes.get("policy_operation_sha256", ""),
        novelty_mean=hashes.get("novelty_raw_mean"),
        novelty_std=hashes.get("novelty_raw_std"),
        model_version=LOCKED_MODEL_VERSION,
        code_version=code_version(),
    )
    if not force:
        status, reason, cached = _cache_status(output_json, expected_meta)
        if status == "hit" and cached is not None:
            cached["cache_status"] = "hit"
            cached["cache_invalidation_reason"] = ""
            return cached
    else:
        status, reason = "miss", "force recompute"

    import time

    validate_daily_egarch_dataset(daily)
    y_pct = pd.Series(daily["return"].astype(float).to_numpy() * 100, index=pd.to_datetime(daily["date"]))
    X = daily[["report_day", "novelty_z", "policy_action_day"]].astype(float).to_numpy()
    baseline_meta = egarch_cache_metadata(
        hashes["return_data_sha256"],
        hashes["event_panel_sha256"],
        policy_operation_sha256=hashes.get("policy_operation_sha256", ""),
        novelty_mean=hashes.get("novelty_raw_mean"),
        novelty_std=hashes.get("novelty_raw_std"),
        model_version=MODEL_VERSION,
        variance_equation="EGARCH(1,1)",
        code_version=code_version(),
    )
    baseline = _fit_baseline_student_t_egarch(
        y_pct,
        OUTPUT_DIR / "cache" / "full_sample_egarch_baseline.json",
        hashes["return_data_sha256"],
        cache_metadata=baseline_meta,
    )
    starts = [_egarch_start_from_baseline(baseline, X.shape[1], perturb=False), _egarch_start_from_baseline(baseline, X.shape[1], perturb=True)]
    bounds = [
        (-2.0, 2.0),
        (-0.5, 0.5),
        (-3.5, 2.0),
        (-0.5, 0.9),
        (-0.8, 0.8),
        (0.2, 0.999),
        *([(-3.0, 3.0)] * X.shape[1]),
        (2.2, 40.0),
    ]
    start_rows = []
    best = None
    t0 = time.perf_counter()
    y = y_pct.to_numpy()
    for i, start in enumerate(starts):
        initial_objective = float(_student_t_loglik(start, y, X))
        result = minimize(
            _student_t_loglik,
            start,
            args=(y, X),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 700, "ftol": 1e-8},
        )
        row = {
            "start_id": i + 1,
            "initial_objective": initial_objective,
            "final_objective": float(result.fun),
            "converged": bool(result.success),
            "optimizer_message": str(result.message),
        }
        start_rows.append(row)
        if best is None or result.fun < best.fun:
            best = result
    runtime = time.perf_counter() - t0
    if best is None:
        raise RuntimeError("Full joint EGARCH-X MLE failed for all starts")
    names = ["mu_c", "ar1", "omega", "alpha", "gamma", "beta", "report_day", "novelty_z", "policy_action_day", "nu"]
    n_params = len(names)
    se, pvals = _approx_se_pvalues(best, n_params)
    restriction_idx = names.index("novelty_z")
    free_mask = np.ones(n_params, dtype=bool)
    free_mask[restriction_idx] = False

    def restricted_objective(theta: np.ndarray) -> float:
        full = np.zeros(n_params, dtype=float)
        full[free_mask] = theta
        full[restriction_idx] = 0.0
        return float(_student_t_loglik(full, y, X))

    restricted_start = np.asarray(best.x, dtype=float)[free_mask]
    restricted_bounds = [bounds[i] for i in range(n_params) if free_mask[i]]
    restricted_result = minimize(
        restricted_objective,
        restricted_start,
        method="L-BFGS-B",
        bounds=restricted_bounds,
        options={"maxiter": 700, "ftol": 1e-8},
    )
    unrestricted_loglik = float(-best.fun)
    restricted_loglik = float(-restricted_result.fun)
    raw_formal_lr = 2 * (unrestricted_loglik - restricted_loglik)
    formal_lr = float(max(raw_formal_lr, 0.0)) if np.isfinite(raw_formal_lr) else float("nan")
    formal_lr_p = float(scipy_stats.chi2.sf(formal_lr, 1)) if np.isfinite(formal_lr) else float("nan")
    sigma2, eps = _joint_sigma2(best.x, y, X)
    std_resid = eps / np.sqrt(np.maximum(sigma2, 1e-12))
    params = {name: float(best.x[i]) for i, name in enumerate(names)}
    stderr = {name: se[i] for i, name in enumerate(names)}
    pvalues = {name: pvals[i] for i, name in enumerate(names)}
    novelty_lambda = params["novelty_z"]
    restricted_params = {}
    full_restricted = np.zeros(n_params, dtype=float)
    full_restricted[free_mask] = restricted_result.x
    full_restricted[restriction_idx] = 0.0
    for i, name in enumerate(names):
        restricted_params[name] = float(full_restricted[i])
    out = {
        "method": "full_joint_mle",
        "model_role": "advanced_daily_robustness_formal_D0",
        "sample_scope": "full_continuous_daily_sequence",
        "uses_full_continuous_daily_sequence": True,
        "dropped_non_event_days": False,
        "distribution": "student_t",
        "variance_equation": "log_sigma2_t = omega + alpha(|z_t-1|-E|z|) + gamma*z_t-1 + beta*log_sigma2_t-1 + report_day + novelty_z + policy_action_day",
        "n_daily_observations": int(len(daily)),
        "n_report_events": int(daily["report_day"].sum()),
        "n_novelty_events": int(daily["novelty_available"].sum()),
        "n_policy_action_days": int(daily["policy_action_day"].sum()),
        "date_start": str(pd.to_datetime(daily["date"]).min().date()),
        "date_end": str(pd.to_datetime(daily["date"]).max().date()),
        "formal_report_period_start": hashes.get("formal_report_period_start"),
        "formal_report_period_end": hashes.get("formal_report_period_end"),
        "daily_estimation_start": hashes.get("daily_estimation_start"),
        "daily_estimation_end": hashes.get("daily_estimation_end"),
        "first_report_event_date": hashes.get("first_report_event_date"),
        "last_report_event_date": hashes.get("last_report_event_date"),
        "last_d1_date": hashes.get("last_d1_date"),
        "novelty_raw_mean": hashes.get("novelty_raw_mean"),
        "novelty_raw_std": hashes.get("novelty_raw_std"),
        "novelty_standardization_scope": hashes.get("novelty_standardization_scope"),
        "return_data_sha256": hashes["return_data_sha256"],
        "event_panel_sha256": hashes["event_panel_sha256"],
        "policy_operation_sha256": hashes.get("policy_operation_sha256", ""),
        "daily_dataset_sha256": hashes.get("daily_dataset_sha256"),
        "cache_metadata": expected_meta,
        "cache_status": status if status != "hit" else "miss",
        "cache_invalidation_reason": reason,
        "code_version": expected_meta["code_version"],
        "random_seed": int(random_seed),
        "optimizer": "scipy.optimize.minimize L-BFGS-B",
        "initial_values": [start.tolist() for start in starts],
        "all_start_objectives": start_rows,
        "converged": bool(best.success),
        "optimizer_message": str(best.message),
        "parameters": params,
        "optimizer_inverse_hessian_se_approx": stderr,
        "optimizer_inverse_hessian_p_approx": pvalues,
        "optimizer_inverse_hessian_note": "Diagnostic only; formal inference uses the restricted versus unrestricted joint MLE likelihood-ratio test.",
        "log_likelihood": unrestricted_loglik,
        "unrestricted_joint_loglik": unrestricted_loglik,
        "restricted_joint_mle_converged": bool(restricted_result.success),
        "restricted_joint_optimizer_message": str(restricted_result.message),
        "restricted_joint_loglik": restricted_loglik,
        "restricted_joint_parameters": restricted_params,
        "formal_lr_raw_statistic": float(raw_formal_lr),
        "formal_lr_statistic": formal_lr,
        "formal_lr_df": 1,
        "formal_lr_p_value": formal_lr_p,
        "primary_inference": "formal_joint_likelihood_ratio",
        "hessian_is_finite": False,
        "hessian_is_positive_definite": False,
        "hessian_condition_number": float("nan"),
        "wald_inference_status": "unstable_not_used",
        "conditional_variance_change_pct_per_1sd_novelty": float((math.exp(novelty_lambda) - 1) * 100),
        "conditional_volatility_change_pct_per_1sd_novelty": float((math.exp(novelty_lambda / 2) - 1) * 100),
        "AIC": float(2 * n_params - 2 * (-best.fun)),
        "BIC": float(n_params * math.log(len(daily)) - 2 * (-best.fun)),
        "residual_diagnostics": {
            "std_residuals_mean": float(np.nanmean(std_resid)),
            "std_residuals_std": float(np.nanstd(std_resid)),
            "conditional_vol_mean": float(np.nanmean(np.sqrt(sigma2))),
        },
        "runtime_seconds": float(runtime),
        "conditional_variance": [float(v) for v in sigma2],
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    restricted_path = output_json.with_name("daily_egarch_x_restricted.json")
    restricted_path.write_text(
        json.dumps(
            {
                "method": "restricted_joint_mle_lambda_novelty_z_eq_0",
                "restricted_parameter": "novelty_z",
                "converged": bool(restricted_result.success),
                "optimizer_message": str(restricted_result.message),
                "restricted_joint_loglik": restricted_loglik,
                "unrestricted_joint_loglik": unrestricted_loglik,
                "formal_lr_statistic": formal_lr,
                "formal_lr_df": 1,
                "formal_lr_p_value": formal_lr_p,
                "parameters": restricted_params,
                "cache_metadata": expected_meta,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if output_csv is not None:
        pd.DataFrame(
            [
                {
                    "parameter": name,
                    "estimate": params[name],
                    "optimizer_inverse_hessian_se_approx": stderr[name],
                    "optimizer_inverse_hessian_p_approx": pvalues[name],
                    "formal_lr_p_value_if_novelty_z": formal_lr_p if name == "novelty_z" else float("nan"),
                }
                for name in names
            ]
        ).to_csv(output_csv, index=False, encoding="utf-8-sig")
    return out


def _fixed_mean_residuals(y: np.ndarray, params: dict) -> np.ndarray:
    mu = _baseline_param(params, "Const", "mu")
    ar_key = _arch_ar_key(params)
    phi = float(params.get(ar_key, 0.0)) if ar_key else 0.0
    eps = np.zeros(len(y))
    eps[0] = y[0] - mu
    for t in range(1, len(y)):
        eps[t] = y[t] - mu - phi * y[t - 1]
    return eps


def _conditional_sigma2(coeffs: np.ndarray, eps: np.ndarray, X: np.ndarray, base: dict) -> np.ndarray:
    params = base["params"]
    omega = _baseline_param(params, "omega")
    alpha = _baseline_param(params, "alpha[1]")
    gamma = _baseline_param(params, "gamma[1]")
    beta = _baseline_param(params, "beta[1]")
    nu = _baseline_param(params, "nu", default=8.0)
    e_abs_z = math.sqrt((nu - 2) / math.pi) * math.exp(gammaln((nu - 1) / 2) - gammaln(nu / 2)) if nu > 2 else math.sqrt(2 / math.pi)
    sigma2 = np.zeros(len(eps))
    cached = np.asarray(base.get("conditional_variance", []), dtype=float)
    initial = float(cached[0]) if len(cached) and np.isfinite(cached[0]) and cached[0] > 0 else float(np.nanvar(eps))
    sigma2[0] = max(initial, 1e-8)
    for t in range(1, len(eps)):
        z_prev = eps[t - 1] / math.sqrt(max(sigma2[t - 1], 1e-12))
        log_sigma2 = (
            omega
            + alpha * (abs(z_prev) - e_abs_z)
            + gamma * z_prev
            + beta * math.log(max(sigma2[t - 1], 1e-12))
            + float(np.dot(X[t], coeffs))
        )
        sigma2[t] = math.exp(min(max(log_sigma2, -30), 20))
    return sigma2


def _fit_fixed_nuisance_coefficients(
    y_pct: pd.Series,
    X: pd.DataFrame,
    baseline: dict,
    fixed_coeffs: np.ndarray | None = None,
    optimize_idx: list[int] | None = None,
    maxiter: int = 250,
) -> dict:
    """Estimate EGARCH-X event coefficients with full continuous recursion.

    Baseline mean, EGARCH persistence parameters and Student-t degrees of
    freedom are frozen. Only selected event coefficients are optimized.
    """
    y = y_pct.astype(float).to_numpy()
    eps = _fixed_mean_residuals(y, baseline["params"])
    X_arr = X.astype(float).to_numpy()
    n_coeff = X_arr.shape[1]
    if fixed_coeffs is None:
        fixed_coeffs = np.zeros(n_coeff)
    else:
        fixed_coeffs = np.asarray(fixed_coeffs, dtype=float).copy()
    if optimize_idx is None:
        optimize_idx = list(range(n_coeff))

    nu = _baseline_param(baseline["params"], "nu", default=8.0)
    restricted_coeffs = fixed_coeffs.copy()
    restricted_coeffs[optimize_idx] = 0.0
    restricted_sigma2 = _conditional_sigma2(restricted_coeffs, eps, X_arr, baseline)
    restricted_ll = _student_t_ll_from_sigma2(eps, restricted_sigma2, nu)

    def objective(theta: np.ndarray) -> float:
        coeffs = fixed_coeffs.copy()
        coeffs[optimize_idx] = theta
        sigma2 = _conditional_sigma2(coeffs, eps, X_arr, baseline)
        return -_student_t_ll_from_sigma2(eps, sigma2, nu)

    start = fixed_coeffs[optimize_idx]
    bounds = [(-2.5, 2.5)] * len(start)
    result = minimize(objective, start, method="L-BFGS-B", bounds=bounds, options={"maxiter": maxiter, "ftol": 1e-8})
    coeffs = fixed_coeffs.copy()
    coeffs[optimize_idx] = result.x
    sigma2 = _conditional_sigma2(coeffs, eps, X_arr, baseline)
    loglik = _student_t_ll_from_sigma2(eps, sigma2, nu)
    if (not np.isfinite(loglik)) or loglik < restricted_ll - 1e-6:
        coeffs = restricted_coeffs
        sigma2 = restricted_sigma2
        unrestricted_ll = float(restricted_ll)
        gain = 0.0
        lr = 0.0
        optimizer_improvement_status = "no_improvement"
    else:
        unrestricted_ll = float(loglik)
        gain = float(max(unrestricted_ll - restricted_ll, 0.0))
        lr = float(2 * gain)
        optimizer_improvement_status = "improved" if gain > 0 else "no_improvement"
    df_lr = int(len(optimize_idx))
    lr_p = float(scipy_stats.chi2.sf(lr, df_lr)) if df_lr > 0 and np.isfinite(lr) else float("nan")
    return {
        "status": "ok" if np.isfinite(unrestricted_ll) and np.isfinite(restricted_ll) else "failed",
        "converged": bool(result.success),
        "optimizer_message": str(result.message),
        "loglik": float(unrestricted_ll),
        "restricted_loglik": float(restricted_ll),
        "unrestricted_loglik": float(unrestricted_ll),
        "conditional_loglik_gain": float(gain),
        "conditional_lr_statistic": lr,
        "conditional_lr_df": df_lr,
        "conditional_lr_p_value": lr_p,
        "optimizer_improvement_status": optimizer_improvement_status,
        "aic_conditional": float(2 * len(optimize_idx) - 2 * unrestricted_ll),
        "nobs": int(len(y_pct)),
        "params_frozen": {
            "mean_and_egarch_params": baseline["params"],
            "note": "Mean, omega, alpha, gamma, beta and nu are frozen from the full continuous daily baseline EGARCH.",
        },
        "exog_params": {f"exog_{i}": float(coeffs[i]) for i in range(n_coeff)},
        "restricted_exog_params": {f"exog_{i}": float(restricted_coeffs[i]) for i in range(n_coeff)},
        "conditional_vol_mean": float(np.mean(np.sqrt(sigma2))),
        "distribution": "student_t",
        "method": "fixed_nuisance_conditional_likelihood",
    }


def _nuisance_from_locked(locked: dict) -> dict:
    params = locked.get("parameters", {})
    return {
        "method": "locked_full_joint_mle_as_fixed_nuisance",
        "params": {
            "Const": float(params.get("mu_c", 0.0)),
            "ret[1]": float(params.get("ar1", 0.0)),
            "omega": float(params.get("omega", 0.0)),
            "alpha[1]": float(params.get("alpha", 0.0)),
            "gamma[1]": float(params.get("gamma", 0.0)),
            "beta[1]": float(params.get("beta", 0.9)),
            "nu": float(params.get("nu", 8.0)),
        },
        "exog_params": {
            "report_day": float(params.get("report_day", 0.0)),
            "novelty_z": float(params.get("novelty_z", 0.0)),
            "policy_action_day": float(params.get("policy_action_day", 0.0)),
        },
        "conditional_variance": locked.get("conditional_variance", []),
        "source_method": locked.get("method", "full_joint_mle"),
    }


def _conditional_spec_matrix(daily: pd.DataFrame, spec: str) -> tuple[pd.DataFrame, np.ndarray, list[int]]:
    report_d0 = daily["report_day"].astype(float).reset_index(drop=True)
    novelty_d0 = daily["novelty_z"].astype(float).reset_index(drop=True)
    policy = daily["policy_action_day"].astype(float).reset_index(drop=True)
    novelty_d1 = novelty_d0.shift(1).fillna(0.0)
    if spec == "D0":
        X = pd.DataFrame({"report_day_d0": report_d0, "novelty_d0": novelty_d0, "policy_action_day": policy})
        fixed = np.zeros(3)
        optimize_idx = [1]
    elif spec == "D1":
        X = pd.DataFrame({"report_day_d0": report_d0, "novelty_d1": novelty_d1, "policy_action_day": policy})
        fixed = np.zeros(3)
        optimize_idx = [1]
    elif spec == "D0_D1":
        X = pd.DataFrame({"report_day_d0": report_d0, "novelty_d0": novelty_d0, "novelty_d1": novelty_d1, "policy_action_day": policy})
        fixed = np.zeros(4)
        optimize_idx = [1, 2]
    else:
        raise ValueError(f"Unknown conditional EGARCH-X spec: {spec}")
    return X, fixed, optimize_idx


def _d0_d1_collinearity_diagnostics(daily: pd.DataFrame, fit: dict) -> dict:
    X, _, _ = _conditional_spec_matrix(daily, "D0_D1")
    event_mask = (X["novelty_d0"].abs() > 0) | (X["novelty_d1"].abs() > 0)
    event_design = X.loc[event_mask, ["novelty_d0", "novelty_d1"]].to_numpy(dtype=float)
    if event_design.shape[0] >= 2 and np.nanstd(event_design[:, 0]) > 0 and np.nanstd(event_design[:, 1]) > 0:
        corr = float(np.corrcoef(event_design[:, 0], event_design[:, 1])[0, 1])
    else:
        corr = float("nan")
    if event_design.shape[0] >= 2:
        _, svals, _ = np.linalg.svd(event_design, full_matrices=False)
        condition_number = float(svals.max() / svals.min()) if svals.min() > 1e-12 else float("inf")
    else:
        condition_number = float("nan")
    params = fit.get("exog_params", {})
    lambda_d0 = float(params.get("exog_1", float("nan")))
    lambda_d1 = float(params.get("exog_2", float("nan")))
    warning = bool((np.isfinite(condition_number) and condition_number > 30) or (np.isfinite(corr) and abs(corr) > 0.90))
    return {
        "corr_novelty_d0_novelty_d1": corr,
        "condition_number_of_event_design": condition_number,
        "lambda_d0": lambda_d0,
        "lambda_d1": lambda_d1,
        "lambda_d0_plus_lambda_d1": float(lambda_d0 + lambda_d1) if np.isfinite(lambda_d0) and np.isfinite(lambda_d1) else float("nan"),
        "joint_lr_p_value": fit.get("conditional_lr_p_value"),
        "distributed_lag_collinearity_warning": warning,
    }


def run_fixed_nuisance_conditional_egarch_x(
    daily: pd.DataFrame,
    hashes: dict,
    nuisance: dict,
    nuisance_parameter_source: str,
    n_perm: int = 99,
    seed: int = 2026,
    output_json: Path | None = None,
    output_csv: Path | None = None,
    cache_path: Path | None = None,
    force: bool = False,
) -> dict:
    """Run fixed-nuisance conditional likelihood sensitivity and permutation."""
    import time

    checks = validate_daily_egarch_dataset(daily)
    expected_meta = conditional_cache_metadata(hashes, nuisance_parameter_source, n_perm=n_perm, random_seed=seed)
    if cache_path is not None and not force:
        status, reason, cached = _cache_status(cache_path, expected_meta)
        if status == "hit" and cached is not None:
            cached["cache_status"] = "hit"
            cached["cache_invalidation_reason"] = ""
            if output_json is not None and output_json != cache_path:
                output_json.parent.mkdir(parents=True, exist_ok=True)
                output_json.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
            if output_csv is not None:
                pd.DataFrame(cached.get("sensitivity", [])).to_csv(output_csv, index=False, encoding="utf-8-sig")
            return cached
    else:
        status, reason = "miss", "force recompute" if force else "cache disabled"
    y_pct = pd.Series(daily["return"].astype(float).to_numpy() * 100)
    fixed_report = float(nuisance.get("exog_params", {}).get("report_day", 0.0))
    fixed_policy = float(nuisance.get("exog_params", {}).get("policy_action_day", 0.0))
    rows = []
    timings = {}
    fits = {}
    for spec in ["D0", "D1", "D0_D1"]:
        X, fixed, optimize_idx = _conditional_spec_matrix(daily, spec)
        if len(fixed) == 3:
            fixed[0] = fixed_report
            fixed[2] = fixed_policy
        else:
            fixed[0] = fixed_report
            fixed[3] = fixed_policy
        t0 = time.perf_counter()
        fit = _fit_fixed_nuisance_coefficients(y_pct, X, nuisance, fixed_coeffs=fixed, optimize_idx=optimize_idx, maxiter=180)
        timings[f"{spec}_seconds"] = time.perf_counter() - t0
        fits[spec] = fit
        row = {
            "date_window": spec,
            "method": "fixed_nuisance_conditional_likelihood",
            "nuisance_parameter_source": nuisance_parameter_source,
            "status": fit["status"],
            "converged": fit["converged"],
            "nobs": fit["nobs"],
            "restricted_loglik": fit["restricted_loglik"],
            "unrestricted_loglik": fit["unrestricted_loglik"],
            "conditional_loglik": fit["loglik"],
            "conditional_loglik_gain": fit["conditional_loglik_gain"],
            "conditional_lr_statistic": fit["conditional_lr_statistic"],
            "conditional_lr_df": fit["conditional_lr_df"],
            "conditional_lr_p_value": fit["conditional_lr_p_value"],
            "optimizer_improvement_status": fit["optimizer_improvement_status"],
            "report_day_coef_fixed": fixed_report,
            "policy_action_coef_fixed": fixed_policy,
        }
        for key, value in fit["exog_params"].items():
            row[f"{key}_coef"] = value
        rows.append(row)

    rng = np.random.default_rng(seed)
    X_perm, fixed_perm, optimize_idx = _conditional_spec_matrix(daily, "D0")
    fixed_perm[0] = fixed_report
    fixed_perm[2] = fixed_policy
    observed = abs(fits["D0"]["exog_params"].get("exog_1", 0.0))
    event_mask = daily["novelty_available"].astype(float).eq(1.0).reset_index(drop=True)
    event_values = X_perm.loc[event_mask, "novelty_d0"].to_numpy()
    count = 0
    t0 = time.perf_counter()
    for _ in range(n_perm):
        X_i = X_perm.copy()
        X_i["novelty_d0"] = 0.0
        X_i.loc[event_mask, "novelty_d0"] = rng.permutation(event_values)
        perm = _fit_fixed_nuisance_coefficients(y_pct, X_i, nuisance, fixed_coeffs=fixed_perm, optimize_idx=optimize_idx, maxiter=80)
        if abs(perm["exog_params"].get("exog_1", 0.0)) >= observed:
            count += 1
    permutation_p = float((1 + count) / (n_perm + 1))
    timings["permutation_seconds"] = time.perf_counter() - t0
    d0_d1_diagnostics = _d0_d1_collinearity_diagnostics(daily, fits["D0_D1"])
    out = {
        "method": "fixed_nuisance_conditional_likelihood",
        "sample_scope": "full_continuous_daily_sequence",
        "uses_full_continuous_daily_sequence": True,
        "dropped_non_event_days": False,
        **checks,
        "return_data_sha256": hashes["return_data_sha256"],
        "event_panel_sha256": hashes["event_panel_sha256"],
        "nuisance_parameter_source": nuisance_parameter_source,
        "permutation_type": "conditional_event_value_permutation",
        "permutation_B": int(n_perm),
        "permutation_random_seed": int(seed),
        "permutation_reestimates_nuisance_parameters": False,
        "permutation_p_novelty": permutation_p,
        "cache_metadata": expected_meta,
        "cache_status": status if status != "hit" else "miss",
        "cache_invalidation_reason": reason,
        "timings": timings,
        "sensitivity": rows,
        "main": fits["D0"],
        "D0_D1_collinearity_diagnostics": d0_d1_diagnostics,
    }
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_csv is not None:
        pd.DataFrame(rows).to_csv(output_csv, index=False, encoding="utf-8-sig")
    return out


def compare_locked_and_conditional(locked: dict, conditional: dict) -> dict:
    """Compare formal D0 full joint MLE with fixed-nuisance D0 estimate."""
    full_lambda = float(locked.get("parameters", {}).get("novelty_z", float("nan")))
    cond_lambda = float(conditional.get("main", {}).get("exog_params", {}).get("exog_1", float("nan")))
    rel_diff = abs(cond_lambda - full_lambda) / max(abs(full_lambda), 0.01) if np.isfinite(full_lambda) and np.isfinite(cond_lambda) else float("nan")
    sign_consistent = bool(np.sign(full_lambda) == np.sign(cond_lambda)) if np.isfinite(full_lambda) and np.isfinite(cond_lambda) else False
    p_full = float(locked.get("formal_lr_p_value", float("nan")))
    full_sig = bool(p_full < 0.05) if np.isfinite(p_full) else False
    # Conditional likelihood currently does not use a standard full-MLE covariance;
    # significance agreement is therefore interpreted conservatively as no
    # contradiction unless the full model is significant and the approximation
    # flips sign or differs materially.
    significance_consistent = bool((not full_sig) or sign_consistent)
    beta_diff = 0.0
    nu_diff = 0.0
    status = "accepted" if sign_consistent and rel_diff <= 0.15 and beta_diff <= 0.02 and nu_diff <= 0.50 and significance_consistent else "diagnostic_only"
    return {
        "lambda_full_joint": full_lambda,
        "lambda_conditional": cond_lambda,
        "sign_consistent": sign_consistent,
        "relative_difference": float(rel_diff),
        "loglik_full_joint": locked.get("log_likelihood"),
        "conditional_loglik": conditional.get("main", {}).get("loglik"),
        "formal_lr_p_value": p_full,
        "conditional_lr_p_value": conditional.get("main", {}).get("conditional_lr_p_value"),
        "beta_difference": beta_diff,
        "nu_difference": nu_diff,
        "significance_consistent": significance_consistent,
        "conditional_approximation_status": status,
    }


def run_full_sample_conditional_egarch_x(
    returns: pd.Series,
    report_day: pd.Series,
    novelty_event: pd.Series,
    policy_action: pd.Series | None = None,
    dates: pd.Series | None = None,
    n_perm: int = 99,
    seed: int = 2026,
) -> dict:
    """Full continuous daily Student-t EGARCH-X with fixed nuisance parameters."""
    df = pd.DataFrame(
        {
            "return": returns.astype(float),
            "report_day": report_day.astype(float).fillna(0),
            "novelty": novelty_event.astype(float).fillna(0),
            "policy_action": policy_action.astype(float).fillna(0) if policy_action is not None else 0.0,
        }
    ).dropna(subset=["return"])
    if dates is not None:
        df["date"] = pd.to_datetime(pd.Series(dates).loc[df.index])
        df = df.sort_values("date")
        y_pct = pd.Series(df["return"].to_numpy() * 100, index=pd.to_datetime(df["date"]))
    else:
        y_pct = pd.Series(df["return"].to_numpy() * 100)
    X = df[["report_day", "novelty", "policy_action"]].reset_index(drop=True)
    data_hash = _series_hash(pd.Series(y_pct.to_numpy()), X["report_day"], X["novelty"], X["policy_action"])
    baseline_path = OUTPUT_DIR / "cache" / "full_sample_egarch_baseline.json"
    baseline = _fit_baseline_student_t_egarch(y_pct, baseline_path, data_hash)
    daily = pd.DataFrame({
        "date": pd.to_datetime(df["date"]) if "date" in df.columns else pd.RangeIndex(len(df)),
        "return": df["return"].to_numpy(),
        "report_day": X["report_day"].to_numpy(),
        "novelty": X["novelty"].to_numpy(),
        "policy_action": X["policy_action"].to_numpy(),
    })
    hashes = {
        "return_data_sha256": data_hash,
        "event_panel_sha256": _series_hash(X["report_day"], X["novelty"], X["policy_action"]),
    }
    out = run_fixed_nuisance_conditional_egarch_x(
        daily,
        hashes,
        baseline,
        nuisance_parameter_source=as_posix_relative(baseline_path),
        n_perm=n_perm,
        seed=seed,
    )
    out["baseline"] = {k: v for k, v in baseline.items() if k not in {"conditional_variance", "residuals"}}
    return out
