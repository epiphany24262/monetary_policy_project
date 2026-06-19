from __future__ import annotations

import pandas as pd

from ..config import get_path_config
from ..paths import ROOT


def load_event_calendar() -> pd.DataFrame:
    df = pd.read_csv(ROOT / get_path_config("event_calendar"))
    for col in ["publication_datetime", "bond_event_date", "equity_event_date"]:
        df[col] = pd.to_datetime(df[col])
    return df.sort_values("publication_datetime").reset_index(drop=True)

