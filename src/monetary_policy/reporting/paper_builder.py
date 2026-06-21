from __future__ import annotations

from .journal_paper_builder import build_journal_paper, inspect_journal_pdf


def build_paper(results: dict) -> None:
    build_journal_paper(results)


def inspect_pdf() -> dict:
    return inspect_journal_pdf()
