import pandas as pd

from src.monetary_policy.events.event_calendar import load_event_calendar


def test_bond_and_equity_event_dates_are_separate_and_not_before_publication():
    events = load_event_calendar()
    pub = pd.to_datetime(events["publication_datetime"]).dt.normalize()
    assert (events["bond_event_date"] >= pub).all()
    assert (events["equity_event_date"] >= pub).all()
    assert {"bond_event_date", "equity_event_date"}.issubset(events.columns)

