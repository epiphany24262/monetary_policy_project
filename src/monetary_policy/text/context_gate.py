"""Context-gating rules for policy stance classification."""

from __future__ import annotations

import yaml
from pathlib import Path

from ..paths import DICTIONARY_DIR

RULES_PATH = DICTIONARY_DIR / "pbc_context_rules.yml"

DEFAULT_RULES = {
    "sentiment_gate": {
        "economic_state": {
            "description": "Real economic state descriptors — may be positive or negative without implying policy action",
            "keywords": [
                "经济下行", "经济回升", "增长放缓", "增长加快",
                "需求不足", "需求旺盛", "产能过剩", "供需平衡",
                "出口下滑", "出口增长", "投资回落", "消费恢复",
            ],
        },
        "policy_goal_action": {
            "description": "Policy goals and actions — contain 'support' style words but are procedural, not sentiment-bearing",
            "keywords": [
                "支持实体经济", "促进就业", "提高效率", "完善机制",
                "优化结构", "加强监管", "推动改革", "深化改革",
                "健全制度", "规范发展", "鼓励创新",
            ],
        },
        "factual_statement": {
            "description": "Pure factual statements without sentiment implication",
            "keywords": [
                "同比增长", "环比增长", "累计增长", "比上年",
                "占GDP", "余额为", "增速为", "达到",
            ],
        },
        "mixed_signal": {
            "description": "Sentences containing both positive and negative signals — require holistic reading",
            "keywords": [
                "虽然", "但", "然而", "不过", "压力", "挑战",
            ],
        },
    },
    "stance_gate": {
        "require_monetary_policy_context": {
            "description": "Only sentences touching these concepts enter dovish/hawkish directional judgment",
            "trigger_keywords": [
                "货币政策", "流动性", "货币信贷", "社会融资",
                "准备金率", "政策利率", "公开市场操作", "融资成本",
                "总量调控", "逆周期", "跨周期", "货币调节",
                "信贷投放", "货币供给", "利率水平", "降准",
                "降息", "加息", "货币市场", "再贷款", "再贴现",
            ],
        },
        "default_irrelevant": {
            "description": "These topics default to irrelevant for policy stance",
            "keywords": [
                "财政减税", "产业扶持", "非法集资", "一般金融监管",
                "政府职能", "非货币", "制度建设",
            ],
        },
    },
}


def load_context_rules() -> dict:
    """Load context-gating rules, initialising defaults if missing."""
    if RULES_PATH.exists():
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(DEFAULT_RULES, f, allow_unicode=True, default_flow_style=False)
    return DEFAULT_RULES


def sentence_has_monetary_policy_context(sentence: str, rules: dict | None = None) -> bool:
    """Check whether a sentence involves monetary policy concepts."""
    rules = rules or load_context_rules()
    triggers = rules["stance_gate"]["require_monetary_policy_context"]["trigger_keywords"]
    return any(kw in sentence for kw in triggers)


def sentence_is_default_irrelevant(sentence: str, rules: dict | None = None) -> bool:
    """Check whether a sentence falls into default-irrelevant categories."""
    rules = rules or load_context_rules()
    keywords = rules["stance_gate"]["default_irrelevant"]["keywords"]
    return any(kw in sentence for kw in keywords)


def gate_stance_label(auto_label: str, sentence: str, rules: dict | None = None) -> str:
    """Apply context-gating to an auto-generated stance label.

    If the sentence does not involve monetary policy concepts AND is not
    already auto-labeled as dovish/hawkish by the lexicon, force to
    'irrelevant'.
    """
    if auto_label in ("dovish", "hawkish"):
        return auto_label  # lexicon found explicit directional terms
    if auto_label == "neutral":
        has_context = sentence_has_monetary_policy_context(sentence, rules)
        is_irrelevant = sentence_is_default_irrelevant(sentence, rules)
        if not has_context or is_irrelevant:
            return "irrelevant"
    return auto_label
