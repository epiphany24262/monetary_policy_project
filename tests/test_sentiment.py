import pandas as pd

from src.monetary_policy.text.lexicon import build_combined_lexicon
from src.monetary_policy.text.sentiment import expanding_unexpected, score_text


def test_sentiment_distinguishes_financial_sentiment_and_policy_stance():
    lexicon = build_combined_lexicon()
    score = score_text("更加有力支持稳增长，保持流动性合理充裕。", lexicon)
    assert score["raw_dovish_count"] > score["raw_hawkish_count"]
    assert "normalized_sentiment" in score
    assert "normalized_policy_stance" in score


def test_unexpected_tone_uses_only_past_values():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 99.0])
    first = expanding_unexpected(series, min_history=3)
    changed_future = expanding_unexpected(pd.Series([1.0, 2.0, 3.0, 4.0, -99.0]), min_history=3)
    assert first.loc[3, "expected_tone"] == changed_future.loc[3, "expected_tone"]

