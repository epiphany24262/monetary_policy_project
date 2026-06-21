from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.monetary_policy.analysis.egarch_x import (
    _cache_status,
    _conditional_spec_matrix,
    _fit_fixed_nuisance_coefficients,
    build_daily_egarch_dataset,
    compare_locked_and_conditional,
    egarch_cache_metadata,
)
from src.monetary_policy.data.market_prices import load_stock_prices
from src.monetary_policy.events.event_calendar import load_event_calendar


@pytest.fixture(scope="module")
def daily_dataset():
    stock = load_stock_prices()
    events = load_event_calendar()
    panel = pd.read_csv("data/processed/refactor_stock_event_panel.csv")
    return build_daily_egarch_dataset(stock, events, panel)


def _locked_result() -> dict:
    path = Path("output/results/daily_egarch_x_locked.json")
    assert path.exists(), "Run scripts/run_daily_egarch_x_locked.py --force before EGARCH output tests."
    return json.loads(path.read_text(encoding="utf-8"))


def _conditional_result() -> dict:
    path = Path("output/results/daily_egarch_x_conditional.json")
    assert path.exists(), "Run scripts/run_daily_egarch_x_locked.py --force before EGARCH output tests."
    return json.loads(path.read_text(encoding="utf-8"))


def test_egarch_formal_sample_bounds(daily_dataset):
    _, checks = daily_dataset
    assert checks["date_start"] == checks["daily_estimation_start"] == "2006-01-04"
    assert checks["date_end"] == checks["daily_estimation_end"] == checks["last_d1_date"]
    assert checks["formal_report_period_start"] == "2006Q1"
    assert checks["formal_report_period_end"] == "2025Q4"
    assert checks["last_report_event_date"] == "2026-02-11"
    assert checks["n_daily_observations"] == 4888
    assert checks["uses_full_continuous_daily_sequence"] is True
    assert checks["dropped_non_event_days"] is False


def test_report_day_count_is_80(daily_dataset):
    daily, checks = daily_dataset
    assert int(daily["report_day"].sum()) == 80
    assert checks["n_report_events"] == 80


def test_novelty_available_count_is_79(daily_dataset):
    daily, checks = daily_dataset
    assert int(daily["novelty_available"].sum()) == 79
    assert checks["n_novelty_events"] == 79


def test_novelty_is_event_standardized(daily_dataset):
    daily, checks = daily_dataset
    event_z = daily.loc[daily["novelty_available"].eq(1), "novelty_z"]
    assert len(event_z) == 79
    assert abs(float(event_z.mean())) < 1e-12
    assert abs(float(event_z.std(ddof=1)) - 1.0) < 1e-12
    assert checks["novelty_standardization_scope"] == "79 report events"


def test_daily_policy_action_mapping(daily_dataset):
    daily, checks = daily_dataset
    assert int(daily["policy_action_day"].sum()) == checks["mapped_unique_policy_action_trading_days"]
    assert checks["n_policy_action_days"] == 107
    assert checks["n_policy_action_days"] > checks["n_report_action_nearby_days"]
    assert str(checks["policy_operation_source"]).replace("\\", "/") == "data/processed/policy_operations.csv"


def _toy_baseline(n: int) -> dict:
    return {
        "params": {
            "Const": 0.0,
            "ret[1]": 0.0,
            "omega": -0.20,
            "alpha[1]": 0.08,
            "gamma[1]": -0.02,
            "beta[1]": 0.92,
            "nu": 8.0,
        },
        "conditional_variance": [1.0] * n,
    }


def test_conditional_null_uses_same_spec():
    y = pd.Series(np.sin(np.linspace(0, 4, 80)) * 0.1)
    X = pd.DataFrame(
        {
            "report_day_d0": [1.0 if i in {20, 40, 60} else 0.0 for i in range(80)],
            "novelty_d1": [0.5 if i in {21, 41, 61} else 0.0 for i in range(80)],
            "policy_action_day": [1.0 if i in {10, 30, 50, 70} else 0.0 for i in range(80)],
        }
    )
    fixed = np.array([0.12, 0.0, -0.03])
    fit = _fit_fixed_nuisance_coefficients(y, X, _toy_baseline(len(y)), fixed_coeffs=fixed, optimize_idx=[1], maxiter=10)
    assert fit["restricted_exog_params"]["exog_0"] == pytest.approx(0.12)
    assert fit["restricted_exog_params"]["exog_1"] == pytest.approx(0.0)
    assert fit["restricted_exog_params"]["exog_2"] == pytest.approx(-0.03)
    assert np.isfinite(fit["restricted_loglik"])
    assert np.isfinite(fit["unrestricted_loglik"])


def test_conditional_lr_never_negative():
    y = pd.Series(np.cos(np.linspace(0, 5, 100)) * 0.1)
    X = pd.DataFrame({"report_day_d0": 0.0, "novelty_d0": 0.0, "policy_action_day": 0.0}, index=range(100))
    fit = _fit_fixed_nuisance_coefficients(y, X, _toy_baseline(len(y)), fixed_coeffs=np.zeros(3), optimize_idx=[1], maxiter=5)
    assert fit["conditional_lr_statistic"] >= 0
    assert fit["conditional_loglik_gain"] >= 0
    assert fit["conditional_lr_df"] == 1


def test_d1_keeps_report_day_at_d0(daily_dataset):
    daily, _ = daily_dataset
    X_d1, _, optimize_idx = _conditional_spec_matrix(daily, "D1")
    first_event_idx = int(daily.index[daily["novelty_available"].eq(1)][0])
    assert optimize_idx == [1]
    assert X_d1.loc[first_event_idx, "report_day_d0"] == 1.0
    assert X_d1.loc[first_event_idx + 1, "novelty_d1"] == pytest.approx(daily.loc[first_event_idx, "novelty_z"])


def test_d0_d1_joint_lr():
    conditional = _conditional_result()
    row = next(row for row in conditional["sensitivity"] if row["date_window"] == "D0_D1")
    assert row["conditional_lr_df"] == 2
    assert row["conditional_lr_statistic"] >= 0
    assert 0 <= row["conditional_lr_p_value"] <= 1
    diagnostics = conditional["D0_D1_collinearity_diagnostics"]
    assert "lambda_d0_plus_lambda_d1" in diagnostics
    assert "condition_number_of_event_design" in diagnostics


def test_formal_restricted_joint_mle():
    locked = _locked_result()
    restricted = json.loads(Path("output/results/daily_egarch_x_restricted.json").read_text(encoding="utf-8"))
    assert locked["restricted_joint_mle_converged"] is True
    assert restricted["restricted_parameter"] == "novelty_z"
    assert restricted["restricted_joint_loglik"] == pytest.approx(locked["restricted_joint_loglik"])


def test_formal_lr_statistic():
    locked = _locked_result()
    expected = max(0.0, 2 * (locked["unrestricted_joint_loglik"] - locked["restricted_joint_loglik"]))
    assert locked["formal_lr_statistic"] == pytest.approx(expected)
    assert locked["formal_lr_df"] == 1
    assert 0 <= locked["formal_lr_p_value"] <= 1


def test_optimizer_hessian_not_used_as_primary_pvalue():
    locked = _locked_result()
    assert "optimizer_inverse_hessian_p_approx" in locked
    assert locked["primary_inference"] == "formal_joint_likelihood_ratio"
    assert "p_values" not in locked
    assert locked["wald_inference_status"] == "unstable_not_used"


def test_cache_invalidates_on_code_change(tmp_path: Path):
    expected = egarch_cache_metadata("return_hash_a", "event_hash_a", code_version="test")
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"cache_metadata": expected}, ensure_ascii=False), encoding="utf-8")
    status, reason, _ = _cache_status(cache, expected)
    assert status == "hit"
    changed = dict(expected)
    changed["model_code_sha256"] = "changed"
    status, reason, _ = _cache_status(cache, changed)
    assert status == "invalidated"
    assert "model_code_sha256" in reason


def test_benchmark_cannot_pass_with_failed_subtask():
    benchmark = importlib.import_module("scripts.benchmark_daily_egarch_x")
    status, failed = benchmark._benchmark_status(
        {
            "n_daily_observations": 4888,
            "n_report_events": 80,
            "n_novelty_events": 79,
            "n_policy_action_days": 107,
            "n_report_action_nearby_days": 10,
            "daily_dataset_sha256": "a",
        },
        {
            "cache_metadata": {"daily_dataset_sha256": "a"},
            "sensitivity": [
                {"date_window": "D0", "status": "ok", "restricted_loglik": 1.0, "unrestricted_loglik": 2.0, "conditional_lr_statistic": 2.0, "exog_1_coef": 0.1},
                {"date_window": "D1", "status": "failed", "restricted_loglik": 1.0, "unrestricted_loglik": 1.0, "conditional_lr_statistic": 0.0, "exog_1_coef": 0.0},
                {"date_window": "D0_D1", "status": "ok", "restricted_loglik": 1.0, "unrestricted_loglik": 1.0, "conditional_lr_statistic": 0.0, "exog_1_coef": 0.0, "exog_2_coef": 0.0},
            ],
        },
        {"converged": True},
    )
    assert status == "FAIL"
    assert any("D1 status" in item for item in failed)


def test_conditional_estimate_matches_locked_result():
    locked = _locked_result()
    conditional = _conditional_result()
    comparison = compare_locked_and_conditional(locked, conditional)
    assert comparison["conditional_approximation_status"] in {"accepted", "diagnostic_only"}
    assert np.isfinite(comparison["lambda_full_joint"])
    assert np.isfinite(comparison["lambda_conditional"])


def test_permutation_only_shuffles_event_values():
    conditional = _conditional_result()
    assert conditional["permutation_type"] == "conditional_event_value_permutation"
    assert conditional["permutation_B"] == 99
    assert conditional["permutation_reestimates_nuisance_parameters"] is False


def test_notebook_has_no_outdated_egarch_statement():
    text = Path("notebooks/货币政策沟通与金融市场反应.ipynb").read_text(encoding="utf-8")
    assert "文本变量仅进入ARX均值方程（均值诊断）" not in text
    assert "EGARCH不能解释文本影响条件方差" not in text


def test_paper_has_no_outdated_validation_statement():
    candidates = [
        Path("src/monetary_policy/reporting/paper_builder.py"),
        Path("src/monetary_policy/reporting/journal_paper_builder.py"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in candidates if path.exists())
    assert "26.25%" not in text
    assert "14.17%" not in text
    assert "文档级聚合指标在回归中更为稳健" not in text


def test_final_submission_contains_new_results():
    manifest_path = Path("delivery/FINAL_SUBMISSION_MANIFEST.csv")
    assert manifest_path.exists()
    manifest = pd.read_csv(manifest_path)
    paths = set(manifest["path"])
    required = {
        "output/results/daily_egarch_x_locked.json",
        "output/results/daily_egarch_x_locked.csv",
        "output/results/daily_egarch_x_restricted.json",
        "output/results/daily_egarch_x_conditional.json",
        "output/results/daily_egarch_x_results.json",
        "output/results/daily_egarch_x_benchmark.json",
        "output/tables/table_learning_curve_summary.xlsx",
        "output/tables/table_market_power_analysis.xlsx",
        "data/processed/cross_fitted_sentence_predictions.csv",
        "data/processed/cross_fitted_report_policy_tone.csv",
    }
    assert required.issubset(paths)
