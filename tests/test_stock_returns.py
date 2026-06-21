import pandas as pd

from src.monetary_policy.events.event_windows import window_return


def test_stock_return_windows_have_explicit_names_and_values():
    panel = pd.read_csv("data/processed/refactor_stock_event_panel.csv")
    assert {"return_0_p1", "return_0_p3", "return_m1_p1", "return_m1_p3"}.issubset(panel.columns)
    prices = pd.Series([100, 105, 110, 120, 130])
    assert window_return(prices, 1, 0, 3) == 130 / 105 - 1

