from __future__ import annotations

import pandas as pd

from ..paths import ROOT


def load_annotation_sheet() -> pd.DataFrame:
    return pd.read_excel(ROOT / "data/validation/sentence_annotation.xlsx")
