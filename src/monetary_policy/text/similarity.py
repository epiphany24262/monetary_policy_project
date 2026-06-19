from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .tokenizer import tokenize


def tokenized_text(text: str) -> str:
    return " ".join(tokenize(text))


def adjacent_word_tfidf_similarity(texts: pd.Series) -> pd.Series:
    docs = texts.fillna("").map(tokenized_text).tolist()
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1)
    matrix = vectorizer.fit_transform(docs)
    sims = [np.nan]
    for i in range(1, matrix.shape[0]):
        sims.append(float(cosine_similarity(matrix[i], matrix[i - 1])[0, 0]))
    return pd.Series(sims, index=texts.index)


def adjacent_char_ngram_similarity(texts: pd.Series) -> pd.Series:
    docs = texts.fillna("").tolist()
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=1)
    matrix = vectorizer.fit_transform(docs)
    sims = [np.nan]
    for i in range(1, matrix.shape[0]):
        sims.append(float(cosine_similarity(matrix[i], matrix[i - 1])[0, 0]))
    return pd.Series(sims, index=texts.index)


def adjacent_expanding_word_tfidf_similarity(texts: pd.Series) -> pd.Series:
    """Adjacent cosine similarity using only documents available up to t.

    For row t, fit TF-IDF on docs 0..t, then compare t with t-1 in that
    vocabulary. Missing current or previous texts produce NaN.
    """
    docs = texts.fillna("").map(tokenized_text).tolist()
    sims = [np.nan]
    for i in range(1, len(docs)):
        if not docs[i].strip() or not docs[i - 1].strip():
            sims.append(np.nan)
            continue
        vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1)
        matrix = vectorizer.fit_transform(docs[: i + 1])
        sims.append(float(cosine_similarity(matrix[i], matrix[i - 1])[0, 0]))
    return pd.Series(sims, index=texts.index)
