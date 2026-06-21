import pandas as pd
import pytest

from src.monetary_policy.events.event_windows import realized_volatility, window_return, yield_change_bp


def test_window_return_0_3_uses_event_day_as_base():
    prices = pd.Series([90, 100, 110, 120, 150])
    assert window_return(prices, event_pos=1, start=0, end=3) == 0.5
    assert window_return(prices, event_pos=1, start=-1, end=1) == 110 / 90 - 1


def test_realized_volatility_and_yield_change():
    returns = pd.Series([0.0, 0.01, -0.01, 0.02, 0.0])
    assert realized_volatility(returns, 1, 0, 3) > 0
    yields = pd.Series([1.0, 1.1, 1.2])
    assert yield_change_bp(yields, 0, 0, 2) == pytest.approx(20.0)
