from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .journal_paper_builder import build_journal_paper


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / 'output'
RESULTS = OUTPUT / 'results'
PROCESSED = ROOT / 'data' / 'processed'


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _read_text_validation_report(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')

    def _match(pattern: str, default=None):
        match = re.search(pattern, text)
        if not match:
            return default
        value = match.group(1)
        return float(value) if '.' in value else int(value)

    return {
        'total_sentences': _match(r'\*\*总句子数\*\*: (\d+)', 0),
        'sentiment_accuracy': _match(r'\| 情感 \| ([0-9.]+) \|', 0.0),
        'stance_accuracy': _match(r'\| 政策倾向（四分类诊断） \| ([0-9.]+) \|', 0.0),
        'policy_direction_accuracy': _match(r'\| 政策方向（仅相关句） \| ([0-9.]+) \|', 0.0),
    }


def build_results_from_outputs() -> dict:
    text_features = pd.read_csv(PROCESSED / 'refactor_text_features.csv')
    stock_panel = pd.read_csv(PROCESSED / 'refactor_stock_event_panel.csv')
    curve_daily = pd.read_csv(PROCESSED / 'refactor_yield_curve_daily.csv')
    curve_panel = pd.read_csv(PROCESSED / 'refactor_yield_curve_event_panel.csv')

    main_vol = _read_json(RESULTS / 'stock_volatility_main.json')
    egarch_x = _read_json(RESULTS / 'daily_egarch_x_results.json')
    text_model_summary = _read_json(RESULTS / 'text_model_evaluation.json')

    validation_report = OUTPUT / 'diagnostics' / 'text_validation_report.md'
    text_validation = _read_text_validation_report(validation_report) if validation_report.exists() else {}

    power_path = OUTPUT / 'diagnostics' / 'market_power_analysis.csv'
    if not power_path.exists():
        power_path = OUTPUT / 'tables' / 'table8_market_power.csv'
    power = pd.read_csv(power_path)

    cross_path = RESULTS / 'cross_fitted_bond_exploration.csv'
    cross = pd.read_csv(cross_path) if cross_path.exists() else pd.DataFrame()

    return {
        'text_features': text_features,
        'stock_panel': stock_panel,
        'curve_daily': curve_daily,
        'curve_panel': curve_panel,
        'tables': {},
        'main_vol': main_vol,
        'egarch_x': egarch_x,
        'text_validation': text_validation,
        'text_model_summary': text_model_summary,
        'learning_curves': {},
        'power_results': power.to_dict(orient='records'),
        'cross_fitted_summary': {'bond_exploration': cross.to_dict(orient='records')},
    }


def main() -> dict:
    results = build_results_from_outputs()
    print('Calling build_journal_paper with assembled results...')
    out = build_journal_paper(results)
    print('build_journal_paper result:', out)
    return out


if __name__ == '__main__':
    main()
