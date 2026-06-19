from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..paths import DICTIONARY_DIR, ROOT


EXTERNAL_DIR = DICTIONARY_DIR / "external"
COMBINED_PATH = DICTIONARY_DIR / "combined_refactor_lexicon.csv"


@dataclass(frozen=True)
class Lexicon:
    positive: set[str]
    negative: set[str]
    dovish: set[str]
    hawkish: set[str]
    negations: set[str]
    degree: dict[str, float]
    topics: dict[str, set[str]]


def _clean_words(values: list[str]) -> set[str]:
    out = set()
    for value in values:
        if isinstance(value, str):
            word = value.strip()
            if word and word.lower() != "nan":
                out.add(word)
    return out


def read_jiang_lexicon(path: Path) -> tuple[set[str], set[str]]:
    pos = pd.read_excel(path, sheet_name="positive").iloc[:, 0].dropna().astype(str).tolist()
    neg = pd.read_excel(path, sheet_name="negative").iloc[:, 0].dropna().astype(str).tolist()
    return _clean_words(pos), _clean_words(neg)


def read_du_lexicon(path: Path) -> tuple[set[str], set[str]]:
    pos = pd.read_excel(path, sheet_name="Positive").iloc[:, 0].dropna().astype(str).tolist()
    neg_raw = pd.read_excel(path, sheet_name="Negative")
    neg = [neg_raw.columns[0], *neg_raw.iloc[:, 0].dropna().astype(str).tolist()]
    return _clean_words(pos), _clean_words(neg)


def pbc_domain_words() -> dict[str, set[str]]:
    return {
        "dovish": {
            "宽松",
            "降准",
            "降息",
            "流动性合理充裕",
            "降低融资成本",
            "稳增长",
            "保持货币信贷合理增长",
            "加大支持",
            "精准有力",
            "适度宽松",
        },
        "hawkish": {
            "偏紧",
            "收紧",
            "升息",
            "加息",
            "防止资金空转",
            "不搞大水漫灌",
            "防风险",
            "抑制通胀",
            "去杠杆",
            "稳汇率",
        },
        "growth": {"稳增长", "扩大内需", "实体经济", "就业", "增长", "高质量发展", "融资成本"},
        "inflation": {"通胀", "物价", "价格水平", "CPI", "输入性通胀", "物价稳定"},
        "risk": {"风险", "防风险", "金融风险", "房地产", "地方债务", "不确定性", "外部冲击"},
        "exchange_rate": {"汇率", "人民币汇率", "跨境资本", "外汇市场", "稳汇率"},
        "financial_stability": {"金融稳定", "宏观审慎", "系统性风险", "金融监管", "杠杆率"},
    }


def base_negations() -> set[str]:
    return {"不", "未", "没有", "无", "难以", "防止", "避免", "不能", "不得", "并非"}


def base_degree_words() -> dict[str, float]:
    return {
        "更加": 1.4,
        "更": 1.2,
        "明显": 1.3,
        "显著": 1.4,
        "大幅": 1.6,
        "适度": 1.1,
        "稳步": 1.1,
        "持续": 1.2,
        "坚决": 1.5,
        "有力": 1.3,
    }


def build_combined_lexicon() -> Lexicon:
    jiang_path = EXTERNAL_DIR / "jiang_financial_sentiment.xlsx"
    du_path = EXTERNAL_DIR / "du_financial_sentiment.xlsx"
    jiang_pos, jiang_neg = read_jiang_lexicon(jiang_path)
    du_pos, du_neg = read_du_lexicon(du_path)
    pbc = pbc_domain_words()
    positive = jiang_pos | du_pos | {"稳健", "改善", "恢复", "支持", "增强", "合理充裕"}
    negative = jiang_neg | du_neg | {"下行压力", "不确定性", "冲击", "压力", "风险暴露"}
    lexicon = Lexicon(
        positive=positive,
        negative=negative,
        dovish=pbc["dovish"],
        hawkish=pbc["hawkish"],
        negations=base_negations(),
        degree=base_degree_words(),
        topics={k: v for k, v in pbc.items() if k not in {"dovish", "hawkish"}},
    )
    rows = []
    for category, words in [
        ("positive", positive),
        ("negative", negative),
        ("dovish", lexicon.dovish),
        ("hawkish", lexicon.hawkish),
    ]:
        rows.extend({"word": w, "category": category} for w in sorted(words))
    for topic, words in lexicon.topics.items():
        rows.extend({"word": w, "category": f"topic_{topic}"} for w in sorted(words))
    COMBINED_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).drop_duplicates().to_csv(COMBINED_PATH, index=False, encoding="utf-8-sig")
    return lexicon

