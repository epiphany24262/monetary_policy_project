from __future__ import annotations

import math

import numpy as np
import pandas as pd


def window_value(values: pd.Series, event_pos: int, start: int, end: int) -> tuple[float, float]:
    start_pos = event_pos + start
    end_pos = event_pos + end
    if start_pos < 0 or end_pos >= len(values):
        return math.nan, math.nan
    return float(values.iloc[start_pos]), float(values.iloc[end_pos])


def window_return(prices: pd.Series, event_pos: int, start: int, end: int) -> float:
    start_price, end_price = window_value(prices, event_pos, start, end)
    if not np.isfinite(start_price) or start_price == 0 or not np.isfinite(end_price):
        return math.nan
    return end_price / start_price - 1


def realized_volatility(returns: pd.Series, event_pos: int, start: int, end: int, annualization: int = 252) -> float:
    start_pos = event_pos + start
    end_pos = event_pos + end
    if start_pos < 0 or end_pos >= len(returns):
        return math.nan
    window = returns.iloc[start_pos : end_pos + 1].dropna()
    if len(window) < 2:
        return math.nan
    return float(window.std(ddof=1) * math.sqrt(annualization))


def yield_change_bp(values: pd.Series, event_pos: int, start: int, end: int) -> float:
    start_value, end_value = window_value(values, event_pos, start, end)
    if not np.isfinite(start_value) or not np.isfinite(end_value):
        return math.nan
    return (end_value - start_value) * 100

