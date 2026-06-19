from __future__ import annotations

import pandas as pd


def sorted_dates(df: pd.DataFrame, date_col: str = "date") -> list[pd.Timestamp]:
    return sorted(pd.to_datetime(df[date_col]).drop_duplicates().tolist())


def event_position(dates: list[pd.Timestamp], event_date: pd.Timestamp) -> int:
    event_date = pd.to_datetime(event_date)
    try:
        return dates.index(event_date)
    except ValueError as exc:
        raise KeyError(f"Event date {event_date.date()} is not in trading calendar") from exc

