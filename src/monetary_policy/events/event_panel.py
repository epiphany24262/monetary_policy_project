from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..config import load_config
from ..data.bond_yields import load_bond_yields
from ..data.market_prices import load_stock_prices
from ..sample import filter_formal_sample, post_2019
from .event_calendar import load_event_calendar
from .event_windows import realized_volatility, window_return, yield_change_bp
from .trading_calendar import event_position, sorted_dates


def _event_value(event: pd.Series, name: str):
    if name in event:
        return event[name]
    if f"{name}_x" in event:
        return event[f"{name}_x"]
    if f"{name}_y" in event:
        return event[f"{name}_y"]
    return math.nan


def build_stock_event_panel(text_features: pd.DataFrame) -> pd.DataFrame:
    cfg = load_config()
    stock = load_stock_prices()
    events = load_event_calendar()
    dates = sorted_dates(stock)
    by_event = events.merge(text_features, left_on="event_id", right_on="report_id", how="left")
    by_event = filter_formal_sample(by_event, "report_period_x" if "report_period_x" in by_event.columns else "report_period")
    rows = []
    for idx, event in by_event.iterrows():
        pos = event_position(dates, event["equity_event_date"])
        row = {
            "event_id": event["event_id"],
            "report_period": _event_value(event, "report_period"),
            "publication_datetime": _event_value(event, "publication_datetime"),
            "equity_event_date": event["equity_event_date"],
            "action_nearby_core": int(event["action_nearby"]),
            "action_nearby_extended": int(event.get("action_nearby_extended", event["action_nearby"])),
            "linear_time_trend": idx + 1,
        }
        row["post_2019"] = post_2019(row["report_period"])
        row["centered_time_trend"] = row["linear_time_trend"]
        for col in [
            "similarity_char_ngram",
            "z_similarity_char_ngram",
            "guidance_similarity_expanding_tfidf",
            "guidance_similarity_full_sample_tfidf",
            "guidance_novelty",
            "guidance_novelty_full_sample_tfidf",
            "fulltext_similarity_expanding_tfidf",
            "fulltext_novelty_expanding_tfidf",
            "fulltext_novelty_full_sample_tfidf",
            "guidance_z_sentiment",
            "macro_z_sentiment",
            "guidance_z_policy_stance",
            "macro_z_policy_stance",
            "guidance_unexpected_tone",
            "guidance_attention_growth",
            "guidance_attention_inflation",
            "guidance_attention_risk",
            "guidance_attention_exchange_rate",
            "guidance_attention_financial_stability",
            "report_length",
            "readability",
        ]:
            row[col] = event.get(col, math.nan)
        row["guidance_novelty_x_post_2019"] = row["guidance_novelty"] * row["post_2019"] if pd.notna(row["guidance_novelty"]) else math.nan
        row["guidance_novelty_full_sample_tfidf_x_post_2019"] = (
            row["guidance_novelty_full_sample_tfidf"] * row["post_2019"]
            if pd.notna(row["guidance_novelty_full_sample_tfidf"])
            else math.nan
        )
        row["fulltext_novelty_expanding_tfidf_x_post_2019"] = (
            row["fulltext_novelty_expanding_tfidf"] * row["post_2019"]
            if pd.notna(row["fulltext_novelty_expanding_tfidf"])
            else math.nan
        )
        row["fulltext_novelty_full_sample_tfidf_x_post_2019"] = (
            row["fulltext_novelty_full_sample_tfidf"] * row["post_2019"]
            if pd.notna(row["fulltext_novelty_full_sample_tfidf"])
            else math.nan
        )
        row["pre_event_volatility_20d"] = float(stock["volatility_20d"].iloc[pos - 1]) if pos > 0 else math.nan
        for start, end in cfg["windows"]["stock_returns"]:
            name = f"return_{'m1' if start == -1 else start}_{'p' + str(end) if end >= 0 else 'm' + str(abs(end))}"
            row[name] = window_return(stock["close"], pos, start, end)
        for start, end in cfg["windows"]["stock_realized_volatility"]:
            row[f"rv_{start}_{end}".replace("-", "m").replace("_0_", "_0_").replace("_", "_")] = realized_volatility(
                stock["simple_return"], pos, start, end
            )
        row["rv_0_3"] = realized_volatility(stock["simple_return"], pos, 0, 3)
        row["rv_0_5"] = realized_volatility(stock["simple_return"], pos, 0, 5)
        row["rv_0_10"] = realized_volatility(stock["simple_return"], pos, 0, 10)
        row["log_rv_0_5"] = math.log(row["rv_0_5"]) if row["rv_0_5"] and row["rv_0_5"] > 0 else math.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    out["centered_time_trend"] = out["linear_time_trend"] - out["linear_time_trend"].mean()
    return out


def build_stock_volatility_paths(stock_panel: pd.DataFrame) -> pd.DataFrame:
    stock = load_stock_prices()
    events = load_event_calendar()
    dates = sorted_dates(stock)
    merged = events.merge(stock_panel[["event_id", "guidance_novelty"]], on="event_id", how="left")
    valid = merged.dropna(subset=["guidance_novelty"])
    q_low = valid["guidance_novelty"].quantile(1 / 3)
    q_high = valid["guidance_novelty"].quantile(2 / 3)
    rows = []
    for _, event in valid.iterrows():
        group = "高创新度" if event["guidance_novelty"] >= q_high else "低创新度" if event["guidance_novelty"] <= q_low else "中间组"
        pos = event_position(dates, event["equity_event_date"])
        for rel in range(0, 11):
            p = pos + rel
            if p < len(stock):
                rows.append(
                    {
                        "event_id": event["event_id"],
                        "similarity_group": group,
                        "relative_day": rel,
                        "abs_return": abs(float(stock["simple_return"].iloc[p])),
                    }
                )
    return pd.DataFrame(rows)


def build_yield_curve_event_panel(text_features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = load_config()
    bond = load_bond_yields().copy()
    bond["level"] = bond[["yield_1y", "yield_5y", "yield_10y"]].mean(axis=1)
    bond["slope"] = bond["yield_10y"] - bond["yield_1y"]
    bond["curvature"] = 2 * bond["yield_5y"] - bond["yield_1y"] - bond["yield_10y"]
    events = load_event_calendar()
    dates = sorted_dates(bond)
    by_event = events.merge(text_features, left_on="event_id", right_on="report_id", how="left")
    by_event = filter_formal_sample(by_event, "report_period_x" if "report_period_x" in by_event.columns else "report_period")
    rows = []
    for idx, event in by_event.iterrows():
        pos = event_position(dates, event["bond_event_date"])
        row = {
            "event_id": event["event_id"],
            "report_period": _event_value(event, "report_period"),
            "bond_event_date": event["bond_event_date"],
            "action_nearby_core": int(event["action_nearby"]),
            "action_nearby_extended": int(event.get("action_nearby_extended", event["action_nearby"])),
            "linear_time_trend": idx + 1,
            "guidance_unexpected_tone": event.get("guidance_unexpected_tone", math.nan),
            "guidance_z_policy_stance": event.get("guidance_z_policy_stance", math.nan),
            "guidance_z_sentiment": event.get("guidance_z_sentiment", math.nan),
        }
        row["post_2019"] = post_2019(row["report_period"])
        row["guidance_unexpected_tone_x_post_2019"] = (
            row["guidance_unexpected_tone"] * row["post_2019"] if pd.notna(row["guidance_unexpected_tone"]) else math.nan
        )
        for factor in ["level", "slope", "curvature", "yield_1y", "yield_5y", "yield_10y"]:
            for start, end in cfg["windows"]["yield_curve"]:
                row[f"delta_{factor}_bp_{start}_{end}".replace("-", "m")] = yield_change_bp(bond[factor], pos, start, end)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["centered_time_trend"] = out["linear_time_trend"] - out["linear_time_trend"].mean()
    return bond, out
