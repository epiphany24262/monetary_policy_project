from __future__ import annotations

import pandas as pd

from ..config import get_path_config
from ..paths import ROOT


def load_source_registry() -> pd.DataFrame:
    return pd.read_csv(ROOT / get_path_config("source_registry"))

