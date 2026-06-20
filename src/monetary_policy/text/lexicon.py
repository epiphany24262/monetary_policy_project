from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..paths import DICTIONARY_DIR, OUTPUT_DIR, ROOT


EXTERNAL_DIR = DICTIONARY_DIR / "external"
COMBINED_PATH = DICTIONARY_DIR / "combined_refactor_lexicon.csv"

# Lexicon versioning
LEXICON_VERSION_DIR = DICTIONARY_DIR / "lexicon_versions"
CURRENT_VERSION = 2


@dataclass(frozen=True)
class Lexicon:
    positive: set[str]
    negative: set[str]
    dovish: set[str]
    hawkish: set[str]
    negations: set[str]
    degree: dict[str, float]
    topics: dict[str, set[str]]
    version: int = CURRENT_VERSION
    revision_note: str = ""


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
    """PBC domain-specific lexicon v2.

    v1 → v2 changes (2026-06-20, based on manual annotation of 240 sentences):
      - dovish: +18 terms (recall was ~18%, target ~50%+)
      - hawkish: +18 terms (recall was 0%, target ~30%+)
      - growth: +22 terms (92/151 growth sentences misclassified as "other")
      - inflation: +5 terms
      - risk: +6 terms
      - exchange_rate: +5 terms
      - financial_stability: +9 terms (17/19 misclassified as "risk" due to
        shared vocabulary with risk category)
      - real_estate: added as a separate descriptive attention category for
        housing-market policy language.
    """
    return {
        "dovish": {
            # v1 original
            "宽松", "降准", "降息", "流动性合理充裕", "降低融资成本",
            "稳增长", "保持货币信贷合理增长", "加大支持", "精准有力", "适度宽松",
            # v2 additions — common PBC easing / support expressions
            "逆周期调节", "跨周期调节", "支持实体经济", "降低实际利率",
            "引导融资成本下行", "推动综合融资成本稳中有降", "保持流动性充裕",
            "结构性货币政策工具", "定向降准", "再贷款再贴现", "普惠金融",
            "小微企业", "民营经济", "降低存款准备金率", "下调政策利率",
            "强化支持", "加大力度", "持续发力", "灵活适度", "精准施策",
            "保持信贷平稳增长", "推动经济回升向好", "稳定市场预期",
            "适度增长", "合理充裕",
        },
        "hawkish": {
            # v1 original
            "偏紧", "收紧", "升息", "加息", "防止资金空转",
            "不搞大水漫灌", "防风险", "抑制通胀", "去杠杆", "稳汇率",
            # v2 additions — tightening / restraint expressions
            "从紧", "适度从紧", "控制信贷", "回笼流动性", "上调利率",
            "审慎管理", "宏观审慎管理", "防范过热", "抑制资产泡沫",
            "管好货币闸门", "总量适度", "货币信贷过快增长", "遏制",
            "严控", "压缩信贷", "收紧银根", "房地产金融审慎",
            "防止过度", "加强宏观审慎", "不松不紧", "保持定力",
            "货币供给总量", "闸门",
        },
        "growth": {
            # v1 original
            "稳增长", "扩大内需", "实体经济", "就业", "增长",
            "高质量发展", "融资成本",
            # v2 additions — broader economic growth vocabulary
            "经济增长", "经济平稳", "平稳发展", "经济结构", "产业结构",
            "制造业", "服务业", "消费", "出口", "创新驱动",
            "转型升级", "供给侧", "需求侧", "内需", "财政政策",
            "基础设施", "城镇化", "区域发展", "协调发展", "国民经济",
            "经济发展", "动能", "新动能", "生产效率", "居民收入",
            "投资", "财税政策", "公共产品", "经济结构调整",
            "增长方式转变", "经济发展方式", "结构调整",
        },
        "inflation": {
            # v1 original
            "通胀", "物价", "价格水平", "CPI", "输入性通胀", "物价稳定",
            # v2 additions
            "物价上涨", "通货", "价格稳定", "PPI", "工业品价格",
            "通货膨胀",
        },
        "risk": {
            # v1 original
            "风险", "防风险", "金融风险", "房地产", "地方债务",
            "不确定性", "外部冲击",
            # v2 additions
            "信用风险", "潜在风险", "风险隐患", "风险防范", "风险化解",
            "影子银行", "跨境资本流动风险", "溢出效应",
        },
        "exchange_rate": {
            # v1 original
            "汇率", "人民币汇率", "跨境资本", "外汇市场", "稳汇率",
            # v2 additions
            "人民币", "外汇储备", "跨境资金", "资本流动", "汇率形成机制",
            "国际收支", "外汇管理",
        },
        "financial_stability": {
            # v1 original
            "金融稳定", "宏观审慎", "系统性风险", "金融监管", "杠杆率",
            # v2 additions — stability-specific (differentiating from risk)
            "金融安全", "金融体系", "银行体系", "守住底线",
            "不发生系统性", "维护金融稳定", "存款保险", "金融基础设施",
            "支付体系", "资本充足", "不良贷款", "拨备覆盖",
            "宏观审慎评估", "金融风险防范化解",
        },
        "real_estate": {
            "房地产", "住房", "房价", "商品房", "保障性住房", "租赁住房",
            "个人住房贷款", "住房信贷", "房地产业", "房地产市场", "房地产金融",
            "房地产金融审慎", "保交楼", "房企", "土地市场", "首套房", "二套房",
        },
    }


def base_negations() -> set[str]:
    return {"不", "未", "没有", "无", "难以", "防止", "避免", "不能", "不得", "并非"}


def base_degree_words() -> dict[str, float]:
    return {
        "更加": 1.4, "更": 1.2, "明显": 1.3, "显著": 1.4, "大幅": 1.6,
        "适度": 1.1, "稳步": 1.1, "持续": 1.2, "坚决": 1.5, "有力": 1.3,
    }


# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------


def _version_snapshot_path(version: int) -> Path:
    return LEXICON_VERSION_DIR / f"pbc_domain_v{version}.json"


def save_lexicon_snapshot(lexicon: Lexicon) -> Path:
    """Save a JSON snapshot of the lexicon for version tracking."""
    LEXICON_VERSION_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "version": lexicon.version,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "revision_note": lexicon.revision_note,
        "dovish": sorted(lexicon.dovish),
        "hawkish": sorted(lexicon.hawkish),
        "topics": {k: sorted(v) for k, v in lexicon.topics.items()},
        "negations": sorted(lexicon.negations),
        "degree": lexicon.degree,
    }
    path = _version_snapshot_path(lexicon.version)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _build_change_report(old: dict, new: dict) -> str:
    """Generate a Markdown change report between two lexicon versions."""
    lines = [
        "# PBC Domain Lexicon Change Report",
        "",
        f"**v{old['version']} → v{new['version']}**",
        f"**Saved at**: {new['saved_at']}",
        f"**Note**: {new['revision_note']}",
        "",
        "## Changes by category",
        "",
    ]
    for category in ["dovish", "hawkish"] + [f"topic_{t}" for t in sorted(new.get("topics", {}))]:
        if category.startswith("topic_"):
            old_words = set(old.get("topics", {}).get(category.replace("topic_", ""), []))
            new_words = set(new.get("topics", {}).get(category.replace("topic_", ""), []))
        else:
            old_words = set(old.get(category, []))
            new_words = set(new.get(category, []))
        added = sorted(new_words - old_words)
        removed = sorted(old_words - new_words)
        lines.append(f"### {category}")
        lines.append(f"- Terms before: {len(old_words)}")
        lines.append(f"- Terms after: {len(new_words)}")
        if added:
            lines.append(f"- **Added ({len(added)})**: {', '.join(added)}")
        if removed:
            lines.append(f"- **Removed ({len(removed)})**: {', '.join(removed)}")
        if not added and not removed:
            lines.append("- No changes.")
        lines.append("")
    return "\n".join(lines) + "\n"


def archive_v1_and_save_v2(lexicon: Lexicon) -> None:
    """Archive the v1 snapshot (if not already saved) and save v2."""
    LEXICON_VERSION_DIR.mkdir(parents=True, exist_ok=True)
    v1_path = _version_snapshot_path(1)
    if not v1_path.exists():
        # Build v1 snapshot from the original definitions
        v1_data = {
            "version": 1,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "revision_note": "Original PBC domain lexicon (v1).",
            "dovish": sorted([
                "宽松", "降准", "降息", "流动性合理充裕", "降低融资成本",
                "稳增长", "保持货币信贷合理增长", "加大支持", "精准有力", "适度宽松",
            ]),
            "hawkish": sorted([
                "偏紧", "收紧", "升息", "加息", "防止资金空转",
                "不搞大水漫灌", "防风险", "抑制通胀", "去杠杆", "稳汇率",
            ]),
            "topics": {
                "growth": sorted(["稳增长", "扩大内需", "实体经济", "就业", "增长", "高质量发展", "融资成本"]),
                "inflation": sorted(["通胀", "物价", "价格水平", "CPI", "输入性通胀", "物价稳定"]),
                "risk": sorted(["风险", "防风险", "金融风险", "房地产", "地方债务", "不确定性", "外部冲击"]),
                "exchange_rate": sorted(["汇率", "人民币汇率", "跨境资本", "外汇市场", "稳汇率"]),
                "financial_stability": sorted(["金融稳定", "宏观审慎", "系统性风险", "金融监管", "杠杆率"]),
                "real_estate": sorted(["房地产", "住房", "房价", "个人住房贷款", "房地产市场"]),
            },
            "negations": sorted(base_negations()),
            "degree": base_degree_words(),
        }
        v1_path.write_text(json.dumps(v1_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save v2
    v2_path = save_lexicon_snapshot(lexicon)

    # Generate change report
    old = json.loads(v1_path.read_text(encoding="utf-8"))
    new = json.loads(v2_path.read_text(encoding="utf-8"))
    report = _build_change_report(old, new)
    change_report_path = LEXICON_VERSION_DIR / "v1_to_v2_changes.md"
    change_report_path.write_text(report, encoding="utf-8")

    # Also save to diagnostics
    diag = OUTPUT_DIR / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    shutil.copy2(v2_path, diag / f"lexicon_v2_snapshot.json")
    shutil.copy2(change_report_path, diag / "lexicon_v1_to_v2_changes.md")


# ---------------------------------------------------------------------------
# Combined lexicon builder
# ---------------------------------------------------------------------------


def build_combined_lexicon() -> Lexicon:
    jiang_path = EXTERNAL_DIR / "jiang_financial_sentiment.xlsx"
    du_path = EXTERNAL_DIR / "du_financial_sentiment.xlsx"
    jiang_pos, jiang_neg = read_jiang_lexicon(jiang_path)
    du_pos, du_neg = read_du_lexicon(du_path)
    pbc = pbc_domain_words()
    # General financial sentiment: keep the published dictionaries intact.
    # Sentence-level sentiment accuracy remains low in the current validation
    # file (about 0.30), so lexicon scores are treated as transparent text
    # measurements rather than stand-alone classifiers.
    positive = jiang_pos | du_pos | {"稳健", "改善", "恢复", "支持", "增强", "合理充裕"}
    negative = jiang_neg | du_neg | {"下行压力", "不确定性", "冲击", "压力", "风险暴露"}
    revision_note = (
        "v1→v2: expanded dovish (+18), hawkish (+18), growth (+22), inflation (+5), "
        "risk (+6), exchange_rate (+5), financial_stability (+9), real_estate (+17) based on 240-sentence "
        "manual annotation validation. External sentiment dictionaries (Jiang, Du) unchanged."
    )
    lexicon = Lexicon(
        positive=positive,
        negative=negative,
        dovish=pbc["dovish"],
        hawkish=pbc["hawkish"],
        negations=base_negations(),
        degree=base_degree_words(),
        topics={k: v for k, v in pbc.items() if k not in {"dovish", "hawkish"}},
        version=CURRENT_VERSION,
        revision_note=revision_note,
    )
    # Version management: archive v1 and save v2
    archive_v1_and_save_v2(lexicon)
    # Write combined CSV
    rows = []
    for category, words in [
        ("positive", positive), ("negative", negative),
        ("dovish", lexicon.dovish), ("hawkish", lexicon.hawkish),
    ]:
        rows.extend({"word": w, "category": category} for w in sorted(words))
    for topic, words in lexicon.topics.items():
        rows.extend({"word": w, "category": f"topic_{topic}"} for w in sorted(words))
    COMBINED_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).drop_duplicates().to_csv(COMBINED_PATH, index=False, encoding="utf-8-sig")
    return lexicon
