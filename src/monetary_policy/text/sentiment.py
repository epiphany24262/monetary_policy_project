from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from .lexicon import Lexicon, build_combined_lexicon
from .text_cleaner import split_sentences
from .tokenizer import tokenize


TURNING_WORDS = {"但是", "但", "然而", "不过", "同时", "而"}


def _phrase_score(sentence: str, words: set[str], lexicon: Lexicon) -> float:
    score = 0.0
    for word in sorted(words, key=len, reverse=True):
        for match in re.finditer(re.escape(word), sentence):
            prefix = sentence[max(0, match.start() - 8) : match.start()]
            weight = 1.0
            for degree, factor in lexicon.degree.items():
                if degree in prefix:
                    weight *= factor
            if any(neg in prefix for neg in lexicon.negations):
                weight *= -1
            if any(turn in prefix for turn in TURNING_WORDS):
                weight *= 1.15
            score += weight
    return score


def _token_score(sentence: str, words: set[str], lexicon: Lexicon) -> float:
    tokens = tokenize(sentence, stopwords=set())
    score = 0.0
    for i, token in enumerate(tokens):
        if token not in words:
            continue
        prefix_tokens = tokens[max(0, i - 3) : i]
        prefix = "".join(prefix_tokens)
        weight = 1.0
        for degree, factor in lexicon.degree.items():
            if degree in prefix:
                weight *= factor
        if any(neg in prefix for neg in lexicon.negations):
            weight *= -1
        if any(turn in prefix for turn in TURNING_WORDS):
            weight *= 1.15
        score += weight
    return score


def score_text(text: str, lexicon: Lexicon | None = None) -> dict[str, float]:
    lexicon = lexicon or build_combined_lexicon()
    sentences = split_sentences(text)
    raw_positive = raw_negative = raw_dovish = raw_hawkish = 0.0
    topic_counts = {name: 0.0 for name in lexicon.topics}
    for sent in sentences:
        raw_positive += _token_score(sent, lexicon.positive, lexicon)
        raw_negative += _token_score(sent, lexicon.negative, lexicon)
        raw_dovish += _phrase_score(sent, lexicon.dovish, lexicon)
        raw_hawkish += _phrase_score(sent, lexicon.hawkish, lexicon)
        for topic, words in lexicon.topics.items():
            topic_counts[topic] += sum(sent.count(word) for word in words)
    effective_chars = max(len(text or ""), 1)
    sentiment = (raw_positive - raw_negative) / effective_chars * 1000
    stance = (raw_dovish - raw_hawkish) / effective_chars * 1000
    out = {
        "raw_positive_count": raw_positive,
        "raw_negative_count": raw_negative,
        "raw_dovish_count": raw_dovish,
        "raw_hawkish_count": raw_hawkish,
        "normalized_sentiment": sentiment,
        "normalized_policy_stance": stance,
        "effective_chars": effective_chars,
        "sentence_count": len(sentences),
    }
    for topic, count in topic_counts.items():
        out[f"attention_{topic}"] = count / effective_chars * 1000
    return out


def zscore_by_section(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        z_col = "z_" + col.replace("normalized_", "")
        out[z_col] = out.groupby("section")[col].transform(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1.0))
    return out


def expanding_unexpected(series: pd.Series, min_history: int = 6) -> pd.DataFrame:
    values = series.astype(float).reset_index(drop=True)
    expected = []
    methods = []
    for i, value in enumerate(values):
        hist = values.iloc[:i].dropna()
        if pd.isna(value):
            expected.append(math.nan)
            methods.append("missing_actual")
            continue
        if len(hist) < min_history:
            expected.append(float(hist.iloc[-1]) if len(hist) else math.nan)
            methods.append("last_available" if len(hist) else "insufficient_history")
            continue
        y = hist.iloc[1:].to_numpy()
        x = hist.iloc[:-1].to_numpy()
        if np.nanstd(x) == 0:
            expected.append(float(np.nanmean(hist)))
            methods.append("historical_mean_constant")
            continue
        beta, alpha = np.polyfit(x, y, 1)
        expected.append(float(alpha + beta * hist.iloc[-1]))
        methods.append("expanding_ar1")
    exp = pd.Series(expected, index=series.index)
    return pd.DataFrame({"expected_tone": exp, "unexpected_tone": series - exp, "expected_method": methods})
