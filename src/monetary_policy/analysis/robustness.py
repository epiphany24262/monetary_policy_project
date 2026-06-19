from __future__ import annotations

import pandas as pd
from statsmodels.stats.multitest import multipletests

from .regressions import ols_hc3, result_row


def similarity_robustness(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for x in [
        "guidance_novelty",
        "fulltext_novelty_expanding_tfidf",
        "guidance_novelty_full_sample_tfidf",
        "fulltext_novelty_full_sample_tfidf",
        "z_similarity_char_ngram",
    ]:
        if x not in panel.columns:
            continue
        result = ols_hc3(
            panel,
            "log_rv_0_5",
            [x, "pre_event_volatility_20d", "action_nearby_core", "post_2019", f"{x}_x_post_2019" if f"{x}_x_post_2019" in panel.columns else "centered_time_trend"],
        )
        rows.append(result_row(result, x, "similarity_robustness"))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["p_value_holm"] = multipletests(out["p_value"].fillna(1.0), method="holm")[1]
    return out
