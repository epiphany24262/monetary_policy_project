import pandas as pd


def test_yield_curve_factor_formulas():
    daily = pd.read_csv("data/processed/refactor_yield_curve_daily.csv")
    row = daily.iloc[-1]
    assert abs(row["level"] - (row["yield_1y"] + row["yield_5y"] + row["yield_10y"]) / 3) < 1e-12
    assert abs(row["slope"] - (row["yield_10y"] - row["yield_1y"])) < 1e-12
    assert abs(row["curvature"] - (2 * row["yield_5y"] - row["yield_1y"] - row["yield_10y"])) < 1e-12


def test_yield_curve_panel_uses_formal_sample_and_interaction():
    panel = pd.read_csv("data/processed/refactor_yield_curve_event_panel.csv")
    assert len(panel) == 80
    assert "2026Q1" not in set(panel["report_period"])
    assert {"guidance_unexpected_tone", "post_2019", "guidance_unexpected_tone_x_post_2019", "action_nearby_core"}.issubset(panel.columns)
