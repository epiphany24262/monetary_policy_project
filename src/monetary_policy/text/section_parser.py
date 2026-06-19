from __future__ import annotations

import pandas as pd

from ..data.pbc_reports import load_section_texts


def load_named_sections() -> pd.DataFrame:
    return load_section_texts()

