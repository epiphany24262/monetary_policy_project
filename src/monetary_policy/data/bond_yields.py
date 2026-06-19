from __future__ import annotations

import pandas as pd

from ..config import get_path_config
from ..paths import ROOT


def load_bond_yields() -> pd.DataFrame:
    df = pd.read_csv(ROOT / get_path_config("bond_yields"), parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)

