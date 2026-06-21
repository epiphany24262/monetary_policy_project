from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.monetary_policy.analysis.egarch_x import (  # noqa: E402
    _fit_baseline_student_t_egarch,
    build_daily_egarch_dataset,
    code_version,
    egarch_cache_metadata,
    run_fixed_nuisance_conditional_egarch_x,
)
from src.monetary_policy.data.market_prices import load_stock_prices  # noqa: E402
from src.monetary_policy.events.event_calendar import load_event_calendar  # noqa: E402
from src.monetary_policy.paths import OUTPUT_DIR, PROCESSED_DIR, RESULTS_DIR, as_posix_relative  # noqa: E402


def _finite(value) -> bool:
    try:
        return value is not None and pd.notna(float(value))
    except (TypeError, ValueError):
        return False


def _benchmark_status(hashes: dict, conditional: dict, baseline: dict) -> tuple[str, list[str]]:
    failed: list[str] = []
    if hashes.get("n_daily_observations", 0) < 4500:
        failed.append("daily sequence too short")
    if hashes.get("n_report_events") != 80:
        failed.append("report event count is not 80")
    if hashes.get("n_novelty_events") != 79:
        failed.append("novelty event count is not 79")
    if hashes.get("n_policy_action_days", 0) <= hashes.get("n_report_action_nearby_days", 0):
        failed.append("policy_action_day does not exceed report_action_nearby_core days")
    if not baseline.get("converged"):
        failed.append("baseline EGARCH did not converge")
    for row in conditional.get("sensitivity", []):
        spec = row.get("date_window")
        if row.get("status") != "ok":
            failed.append(f"{spec} status is not ok")
        if not _finite(row.get("restricted_loglik")) or not _finite(row.get("unrestricted_loglik")):
            failed.append(f"{spec} likelihood is not finite")
        if not _finite(row.get("conditional_lr_statistic")) or float(row.get("conditional_lr_statistic")) < -1e-9:
            failed.append(f"{spec} LR is negative or non-finite")
        for key, value in row.items():
            if key.endswith("_coef") and not _finite(value):
                failed.append(f"{spec} {key} is not finite")
    specs = {row.get("date_window") for row in conditional.get("sensitivity", [])}
    for spec in {"D0", "D1", "D0_D1"} - specs:
        failed.append(f"{spec} missing")
    if conditional.get("cache_metadata", {}).get("daily_dataset_sha256") != hashes.get("daily_dataset_sha256"):
        failed.append("conditional cache metadata daily hash mismatch")
    return ("PASS" if not failed else "FAIL", failed)


def main() -> None:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    stock = load_stock_prices()
    events = load_event_calendar()
    stock_panel = pd.read_csv(PROCESSED_DIR / "stock_event_panel.csv")
    daily, hashes = build_daily_egarch_dataset(stock, events, stock_panel)
    timings["load_and_construct_seconds"] = time.perf_counter() - t0

    y_pct = pd.Series(daily["return"].to_numpy() * 100, index=pd.to_datetime(daily["date"]))
    baseline_meta = egarch_cache_metadata(
        hashes["return_data_sha256"],
        hashes["event_panel_sha256"],
        policy_operation_sha256=hashes.get("policy_operation_sha256", ""),
        novelty_mean=hashes.get("novelty_raw_mean"),
        novelty_std=hashes.get("novelty_raw_std"),
        model_version="daily_egarch_x_v2_full_sequence_fixed_nuisance",
        variance_equation="EGARCH(1,1)",
        code_version=code_version(),
    )
    baseline_path = OUTPUT_DIR / "cache" / "full_sample_egarch_baseline.json"
    t1 = time.perf_counter()
    baseline = _fit_baseline_student_t_egarch(
        y_pct,
        baseline_path,
        hashes["return_data_sha256"],
        cache_metadata=baseline_meta,
    )
    timings["baseline_cache_or_fit_seconds"] = time.perf_counter() - t1

    t2 = time.perf_counter()
    conditional = run_fixed_nuisance_conditional_egarch_x(
        daily,
        hashes,
        baseline,
        nuisance_parameter_source=as_posix_relative(baseline_path),
        n_perm=99,
        seed=2026,
        output_json=RESULTS_DIR / "daily_egarch_x_benchmark_conditional.json",
        output_csv=RESULTS_DIR / "daily_egarch_x_benchmark_conditional.csv",
    )
    timings["conditional_total_seconds"] = time.perf_counter() - t2
    status, failed_checks = _benchmark_status(hashes, conditional, baseline)

    summary = {
        "status": status,
        "failed_checks": failed_checks,
        "complete_daily_sequence": {
            "n_daily_observations": hashes["n_daily_observations"],
            "n_report_events": hashes["n_report_events"],
            "n_novelty_events": hashes["n_novelty_events"],
            "n_policy_action_days": hashes["n_policy_action_days"],
            "n_report_action_nearby_days": hashes["n_report_action_nearby_days"],
            "date_start": hashes["date_start"],
            "date_end": hashes["date_end"],
            "daily_estimation_start": hashes["daily_estimation_start"],
            "daily_estimation_end": hashes["daily_estimation_end"],
            "first_report_event_date": hashes["first_report_event_date"],
            "last_report_event_date": hashes["last_report_event_date"],
            "last_d1_date": hashes["last_d1_date"],
            "uses_full_continuous_daily_sequence": True,
            "dropped_non_event_days": False,
        },
        "novelty_standardization": {
            "novelty_raw_mean": hashes["novelty_raw_mean"],
            "novelty_raw_std": hashes["novelty_raw_std"],
            "scope": hashes["novelty_standardization_scope"],
        },
        "policy_operation_mapping": {
            "mapped_unique_policy_action_trading_days": hashes["mapped_unique_policy_action_trading_days"],
            "policy_operation_source": hashes["policy_operation_source"],
            "policy_operation_mapping_rule": hashes["policy_operation_mapping_rule"],
        },
        "cache_status": baseline.get("cache_status"),
        "cache_invalidation_reason": baseline.get("cache_invalidation_reason"),
        "timings": {**timings, **conditional.get("timings", {})},
        "D0_conditional_novelty_coef": conditional["sensitivity"][0].get("exog_1_coef"),
        "D1_conditional_novelty_coef": conditional["sensitivity"][1].get("exog_1_coef"),
        "D0_D1_conditional_novelty_d0_coef": conditional["sensitivity"][2].get("exog_1_coef"),
        "D0_D1_conditional_novelty_d1_coef": conditional["sensitivity"][2].get("exog_2_coef"),
        "D0_D1_collinearity_diagnostics": conditional.get("D0_D1_collinearity_diagnostics"),
        "permutation_p_novelty": conditional.get("permutation_p_novelty"),
        "permutation_type": conditional.get("permutation_type"),
    }
    out_path = RESULTS_DIR / "daily_egarch_x_benchmark.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
