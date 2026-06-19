from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([。！？；])", r"\1\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    parts = re.split(r"(?<=[。！？；])\s*", normalized)
    return [p.strip() for p in parts if len(p.strip()) >= 4]

