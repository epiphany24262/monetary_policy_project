from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "project.yml"

DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
DICTIONARY_DIR = DATA_DIR / "dictionaries"
OUTPUT_DIR = ROOT / "output"
RESULTS_DIR = OUTPUT_DIR / "results"
FIGURES_DIR = OUTPUT_DIR / "figures"
TABLES_DIR = OUTPUT_DIR / "tables"
NOTEBOOK_DIR = ROOT / "notebooks"
PAPER_DIR = ROOT / "paper"
DELIVERY_DIR = ROOT / "delivery"
FINAL_SUBMISSION_DIR = ROOT / "final_submission"
RESEARCH_DIR = ROOT / "research"


def ensure_dirs() -> None:
    for path in [
        PROCESSED_DIR,
        DICTIONARY_DIR,
        RESULTS_DIR,
        FIGURES_DIR,
        TABLES_DIR,
        NOTEBOOK_DIR,
        PAPER_DIR,
        DELIVERY_DIR,
        FINAL_SUBMISSION_DIR,
        RESEARCH_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)

