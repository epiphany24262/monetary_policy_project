from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.monetary_policy.analysis.egarch_x import (  # noqa: E402
    _nuisance_from_locked,
    build_daily_egarch_dataset,
    compare_locked_and_conditional,
    run_fixed_nuisance_conditional_egarch_x,
    run_locked_full_joint_mle,
)
from src.monetary_policy.data.market_prices import load_stock_prices  # noqa: E402
from src.monetary_policy.events.event_calendar import load_event_calendar  # noqa: E402
from src.monetary_policy.paths import OUTPUT_DIR, PROCESSED_DIR, RESULTS_DIR, as_posix_relative  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run locked full-joint Student-t EGARCH-X D0 MLE.")
    parser.add_argument("--force", action="store_true", help="Ignore cache and recompute the heavy full joint MLE.")
    args = parser.parse_args()

    stock = load_stock_prices()
    events = load_event_calendar()
    stock_panel = pd.read_csv(PROCESSED_DIR / "stock_event_panel.csv")
    daily, hashes = build_daily_egarch_dataset(stock, events, stock_panel)

    locked_json = RESULTS_DIR / "daily_egarch_x_locked.json"
    locked_csv = RESULTS_DIR / "daily_egarch_x_locked.csv"
    locked = run_locked_full_joint_mle(
        daily,
        hashes,
        output_json=locked_json,
        output_csv=locked_csv,
        force=args.force,
        random_seed=2026,
    )

    nuisance = _nuisance_from_locked(locked)
    conditional = run_fixed_nuisance_conditional_egarch_x(
        daily,
        hashes,
        nuisance,
        nuisance_parameter_source=as_posix_relative(locked_json),
        n_perm=99,
        seed=2026,
        output_json=RESULTS_DIR / "daily_egarch_x_conditional.json",
        output_csv=RESULTS_DIR / "daily_egarch_x_conditional.csv",
        cache_path=OUTPUT_DIR / "cache" / "daily_egarch_x_conditional_cache.json",
        force=args.force,
    )
    comparison = compare_locked_and_conditional(locked, conditional)
    combined = {
        "main_model": locked,
        "conditional_model": conditional,
        "comparison": comparison,
        "diagnostics": {
            "role": "advanced_daily_robustness",
            "core_model_remains": "event_level_5day_realized_volatility_ols",
            "method_note": "D0 is full joint MLE. D1, D0_D1 and permutation are fixed-nuisance conditional likelihood diagnostics.",
        },
        "sensitivity": conditional["sensitivity"],
        "permutation_p_novelty": conditional["permutation_p_novelty"],
    }
    (RESULTS_DIR / "daily_egarch_x_results.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "locked_status": locked.get("cache_status"),
        "n_daily_observations": locked.get("n_daily_observations"),
        "n_report_events": locked.get("n_report_events"),
        "n_novelty_events": locked.get("n_novelty_events"),
        "n_policy_action_days": locked.get("n_policy_action_days"),
        "lambda_full_joint": comparison["lambda_full_joint"],
        "lambda_conditional": comparison["lambda_conditional"],
        "formal_lr_p_value": locked.get("formal_lr_p_value"),
        "conditional_approximation_status": comparison["conditional_approximation_status"],
        "permutation_p_novelty": conditional["permutation_p_novelty"],
        "runtime_seconds": locked.get("runtime_seconds"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
