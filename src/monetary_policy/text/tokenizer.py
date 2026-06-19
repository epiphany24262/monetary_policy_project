from __future__ import annotations

import jieba

from ..config import load_config

_INITIALIZED = False


def initialize_tokenizer() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    for term in load_config()["text"]["protected_terms"]:
        jieba.add_word(term, freq=200000)
    _INITIALIZED = True


def tokenize(text: str, stopwords: set[str] | None = None) -> list[str]:
    initialize_tokenizer()
    stop = stopwords if stopwords is not None else set(load_config()["text"]["stopwords"])
    tokens = [tok.strip() for tok in jieba.lcut(text or "")]
    return [tok for tok in tokens if len(tok) > 1 and tok not in stop and not tok.isdigit()]
