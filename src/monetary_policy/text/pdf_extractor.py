from __future__ import annotations

from pathlib import Path


def cleaned_text_preview(path: Path, max_chars: int = 500) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {"path": str(path), "preview": text[:max_chars]}

