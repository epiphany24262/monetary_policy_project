import pandas as pd

from src.monetary_policy.text.similarity import adjacent_word_tfidf_similarity


def test_similarity_compares_adjacent_reports_only():
    texts = pd.Series(["货币政策 稳增长", "货币政策 稳增长", "完全不同 外部冲击"])
    sims = adjacent_word_tfidf_similarity(texts)
    assert pd.isna(sims.iloc[0])
    assert sims.iloc[1] > sims.iloc[2]

