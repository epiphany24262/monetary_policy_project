import numpy as np
import pandas as pd

from src.monetary_policy.analysis.stock_volatility import run_stock_volatility_models


def test_stock_realized_volatility_outputs_exist_and_are_positive():
    panel = pd.read_csv("data/processed/refactor_stock_event_panel.csv")
    assert {"rv_0_3", "rv_0_5", "rv_0_10", "log_rv_0_5", "guidance_novelty", "guidance_novelty_x_post_2019"}.issubset(panel.columns)
    assert (panel["rv_0_5"].dropna() > 0).all()
    assert np.isfinite(panel["log_rv_0_5"].dropna()).all()
    assert len(panel) == 80
    assert "2026Q1" not in set(panel["report_period"])


def test_arx_mean_diagnostic_is_not_run_by_formal_stock_model():
    panel = pd.read_csv("data/processed/refactor_stock_event_panel.csv")
    _, _, diagnostic = run_stock_volatility_models(panel)
    assert diagnostic["status"] == "not_run"
    assert diagnostic["method"] == "arx_mean_equation_diagnostic_disabled"
