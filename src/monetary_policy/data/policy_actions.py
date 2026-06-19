from __future__ import annotations

import pandas as pd

from ..config import get_path_config
from ..paths import ROOT


def load_policy_actions() -> pd.DataFrame:
    return pd.read_csv(ROOT / get_path_config("policy_operations"), parse_dates=["date", "effective_date"])
