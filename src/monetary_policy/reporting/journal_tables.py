from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..config import load_config
from ..paths import OUTPUT_DIR, ROOT, TABLES_DIR


DASH = "—"


@dataclass
class JournalTables:
    table1: pd.DataFrame
    table2: pd.DataFrame
    table3: pd.DataFrame
    table4: pd.DataFrame


def fmt(value, digits: int = 4) -> str:
    try:
        if value is None or pd.isna(value):
            return DASH
        return f"{float(value):.{digits}f}"
    except Exception:
        text = str(value)
        return text if text else DASH


def fmt_int(value) -> str:
    try:
        if value is None or pd.isna(value):
            return DASH
        return str(int(value))
    except Exception:
        return str(value) if str(value) else DASH


def write_journal_tables(results: dict) -> JournalTables:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    tables = JournalTables(
        table1=_build_table1(),
        table2=_build_table2(results),
        table3=_build_table3(),
        table4=_build_table4(results),
    )
    tables.table1.to_csv(TABLES_DIR / "journal_table1_data_sources.csv", index=False, encoding="utf-8-sig")
    tables.table2.to_csv(TABLES_DIR / "journal_table2_text_measurement.csv", index=False, encoding="utf-8-sig")
    tables.table3.to_csv(TABLES_DIR / "journal_table3_stock_volatility.csv", index=False, encoding="utf-8-sig")
    tables.table4.to_csv(TABLES_DIR / "journal_table4_robustness_bond.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(TABLES_DIR / "journal_tables.xlsx") as writer:
        tables.table1.to_excel(writer, sheet_name="table1", index=False)
        tables.table2.to_excel(writer, sheet_name="table2", index=False)
        tables.table3.to_excel(writer, sheet_name="table3", index=False)
        tables.table4.to_excel(writer, sheet_name="table4", index=False)
    return tables


def _source_row(registry: pd.DataFrame, name: str) -> pd.Series:
    hit = registry[registry["dataset_name"].astype(str).eq(name)]
    return hit.iloc[0] if len(hit) else pd.Series(dtype=object)


def _coverage(row: pd.Series, fallback: str) -> str:
    if row.empty:
        return fallback
    start = row.get("coverage_start")
    end = row.get("coverage_end")
    if pd.isna(start) or pd.isna(end):
        return fallback
    return f"{start}-{end}"


def _build_table1() -> pd.DataFrame:
    cfg = load_config()
    registry = pd.read_csv(ROOT / "data" / "source_registry.csv")
    features = pd.read_csv(ROOT / "data" / "processed" / "refactor_text_features.csv")
    formal_n = int(features["in_formal_sample"].sum())
    annotation = pd.read_excel(ROOT / "data" / "validation" / "manual_sentence_annotation_filled.xlsx")
    report_rows = registry[registry["dataset_name"].astype(str).str.startswith("pbc_report_")]
    report_period = f"{cfg['analysis_sample']['start_period']}-{cfg['analysis_sample']['end_period']}（{formal_n}期）"
    stock = _source_row(registry, "csi300_daily_full")
    bond = _source_row(registry, "chinabond_government_yield_full")
    operation = _source_row(registry, "policy_operations_public_interfaces")
    return pd.DataFrame(
        [
            {
                "数据类别": "货币政策报告",
                "主要内容": "中国人民银行季度货币政策执行报告全文、宏观经济章节和政策指引章节",
                "频率": "季度",
                "正式样本期": report_period,
                "研究用途": "构造文本创新度、政策语调和报告发布事件",
            },
            {
                "数据类别": "股票市场",
                "主要内容": "沪深300指数日行情",
                "频率": "日度",
                "正式样本期": _coverage(stock, report_period),
                "研究用途": "计算报告发布后五个交易日实际波动率",
            },
            {
                "数据类别": "国债收益率曲线",
                "主要内容": "1年、5年和10年期中债国债收益率",
                "频率": "日度",
                "正式样本期": _coverage(bond, report_period),
                "研究用途": "构造水平、斜率和曲率的短窗口变化",
            },
            {
                "数据类别": "政策操作",
                "主要内容": "公开政策操作日期与工具信息",
                "频率": "不定期",
                "正式样本期": _coverage(operation, report_period),
                "研究用途": "控制报告发布期附近的政策环境",
            },
            {
                "数据类别": "人工标注",
                "主要内容": f"政策指引句子{len(annotation)}句，包含情感、政策倾向和主题标签",
                "频率": "句子层",
                "正式样本期": f"{annotation['report_period'].min()}-{annotation['report_period'].max()}",
                "研究用途": "验证词典、语境门控和监督分类测度",
            },
        ]
    )


def _build_table2(results: dict) -> pd.DataFrame:
    validation = results["text_validation"]
    model = results["text_model_summary"]
    rows = [
        {"Panel": "Panel A 情感与政策四分类", "方法": "初始词典", "情感准确率": DASH, "情感Macro-F1": DASH, "政策准确率": DASH, "政策Macro-F1": DASH},
        {
            "Panel": "Panel A 情感与政策四分类",
            "方法": "语境门控词典",
            "情感准确率": fmt(validation.get("sentiment_accuracy")),
            "情感Macro-F1": fmt(validation.get("sentiment_macro_f1")),
            "政策准确率": fmt(validation.get("stance_accuracy")),
            "政策Macro-F1": fmt(validation.get("stance_macro_f1")),
        },
        {
            "Panel": "Panel A 情感与政策四分类",
            "方法": "字符TF-IDF与LinearSVC",
            "情感准确率": fmt(model["sentiment_cv"].get("accuracy")),
            "情感Macro-F1": fmt(model["sentiment_cv"].get("macro_f1")),
            "政策准确率": fmt(model["policy_stance_cv"].get("accuracy")),
            "政策Macro-F1": fmt(model["policy_stance_cv"].get("macro_f1")),
        },
        {"Panel": "Panel B 条件政策方向", "方法": "初始词典", "方向准确率": DASH, "方向Macro-F1": DASH},
        {
            "Panel": "Panel B 条件政策方向",
            "方法": "语境门控词典",
            "方向准确率": fmt(validation.get("policy_direction_accuracy")),
            "方向Macro-F1": fmt(validation.get("policy_direction_macro_f1")),
        },
        {
            "Panel": "Panel B 条件政策方向",
            "方法": "字符TF-IDF与LinearSVC",
            "方向准确率": fmt(model["policy_direction_cv"].get("accuracy")),
            "方向Macro-F1": fmt(model["policy_direction_cv"].get("macro_f1")),
        },
    ]
    return pd.DataFrame(rows).fillna(DASH)


def _build_table3() -> pd.DataFrame:
    stock = pd.read_csv(ROOT / "output" / "results" / "stock_volatility_results.csv")
    labels = {
        "full": "基准交互模型中的早期效应",
        "pre_2019": "2019年前",
        "post_2019": "2019年后",
        "covid": "疫情期",
        "non_covid": "非疫情期",
    }
    rows = []
    for key in ["full", "pre_2019", "post_2019", "covid", "non_covid"]:
        row = stock[stock["model"].eq(key)].iloc[0]
        rows.append(
            {
                "样本": labels[key],
                "样本量": fmt_int(row["n"]),
                "创新度系数": fmt(row["beta"]),
                "HC3标准误": fmt(row["se_hc3"]),
                "p值": fmt(row["p_value"]),
            }
        )
    return pd.DataFrame(rows)


def _build_table4(results: dict) -> pd.DataFrame:
    egarch = results["egarch_x"]
    main = egarch.get("main", egarch.get("main_model", {}))
    rows = [
        {
            "Panel": "Panel A Student-t EGARCH-X稳健性",
            "规格": "报告发布当日（联合极大似然估计）",
            "创新度系数": fmt(main.get("parameters", {}).get("novelty_z")),
            "似然比p值": fmt(main.get("formal_lr_p_value")),
            "置换p值": fmt(egarch.get("permutation_p_novelty")),
            "样本量": fmt_int(main.get("n_daily_observations")),
        }
    ]
    for item in egarch.get("sensitivity", []):
        label = {"D0": "报告发布当日（条件似然诊断）", "D1": "报告发布后一交易日", "D0_D1": "当日与次日联合规格"}.get(
            item.get("date_window"), str(item.get("date_window"))
        )
        coef = item.get("exog_1_coef")
        if item.get("date_window") == "D0_D1":
            coef = item.get("exog_1_coef", 0) + item.get("exog_2_coef", 0)
        rows.append(
            {
                "Panel": "Panel A Student-t EGARCH-X稳健性",
                "规格": label,
                "创新度系数": fmt(coef),
                "似然比p值": fmt(item.get("conditional_lr_p_value")),
                "置换p值": DASH,
                "样本量": fmt_int(item.get("nobs")),
            }
        )
    curve = pd.read_csv(ROOT / "output" / "results" / "yield_curve_results.csv")
    curve_labels = {
        "delta_slope_bp_0_3": "收益率曲线斜率",
        "delta_level_bp_0_3": "收益率曲线水平",
        "delta_curvature_bp_0_3": "收益率曲线曲率",
    }
    for dep in ["delta_slope_bp_0_3", "delta_level_bp_0_3", "delta_curvature_bp_0_3"]:
        row = curve[curve["dependent"].eq(dep)].iloc[0]
        rows.append(
            {
                "Panel": "Panel B 国债收益率曲线",
                "被解释变量": curve_labels[dep],
                "样本量": fmt_int(row["n"]),
                "系数": fmt(row["beta"]),
                "HC3标准误": fmt(row["se_hc3"]),
                "p值": fmt(row["p_value"]),
            }
        )
    cross = pd.read_csv(ROOT / "output" / "results" / "cross_fitted_bond_exploration.csv")
    tone_labels = {
        "all_sentence_mean": "全部句子均值",
        "policy_relevant_mean": "政策相关句均值",
        "directional_sentence_mean": "方向性句子均值",
    }
    for key in ["all_sentence_mean", "policy_relevant_mean", "directional_sentence_mean"]:
        row = cross[cross["tone_aggregation"].eq(key)].iloc[0]
        rows.append(
            {
                "Panel": "Panel C 跨拟合政策语调",
                "聚合方式": tone_labels[key],
                "样本量": fmt_int(row["n"]),
                "主效应": fmt(row["coef"]),
                "p值": fmt(row["p_value"]),
                "2019年后总效应": fmt(row["post_2019_total_effect"]),
                "总效应p值": fmt(row["post_2019_total_p_value"]),
            }
        )
    return pd.DataFrame(rows).fillna(DASH)
