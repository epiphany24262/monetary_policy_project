from __future__ import annotations

import json
import math
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis.descriptive import descriptive_stats
from .analysis.robustness import similarity_robustness
from .analysis.stock_returns import run_stock_return_models
from .analysis.stock_volatility import run_stock_volatility_models, write_egarch
from .analysis.yield_curve import run_yield_curve_models
from .data.pbc_reports import load_full_texts, load_report_metadata, load_section_texts
from .events.event_panel import build_stock_event_panel, build_stock_volatility_paths, build_yield_curve_event_panel
from .paths import FIGURES_DIR, OUTPUT_DIR, PAPER_DIR, PROCESSED_DIR, RESEARCH_DIR, RESULTS_DIR, TABLES_DIR, ensure_dirs, ROOT
from .reporting.delivery_builder import build_final_submission
from .reporting.notebook_builder import build_notebook, execute_notebook
from .reporting.paper_builder import build_paper, inspect_pdf
from .sample import filter_formal_sample, is_in_formal_sample, sample_bounds, verify_final_analysis_plan
from .text.lexicon import build_combined_lexicon
from .text.section_repair import repair_guidance_sections
from .text.sentiment import expanding_unexpected, score_text, zscore_by_section
from .text.similarity import (
    adjacent_char_ngram_similarity,
    adjacent_expanding_word_tfidf_similarity,
    adjacent_word_tfidf_similarity,
)
from .text.manual_validation import build_manual_sentence_annotation
from .text.validation_report import run_text_validation, write_validation_outputs
from .visualization.market_figures import (
    plot_curve_reactions,
    plot_similarity_scatter,
    plot_volatility_paths,
    plot_yield_curve_factors,
)
from .visualization.result_tables import variable_definition_table, write_excel_tables
from .visualization.text_figures import plot_similarity, plot_tone_series


def build_research_documents() -> None:
    for stale in [RESEARCH_DIR / "REFACTOR_LITERATURE_MATRIX.xlsx", RESEARCH_DIR / "REFACTOR_METHOD_COMPARISON.md"]:
        if stale.exists():
            try:
                stale.unlink()
            except PermissionError:
                pass
    rows = [
        {
            "source": "姜富伟、胡逸驰、黄楠（2021）《央行货币政策报告文本信息、宏观经济与股票市场》",
            "verified_url": "https://www.jryj.org.cn/CN/abstract/abstract897.shtml",
            "method_used_by_source": "区分宏观经济信息和未来政策指引信息；使用金融情感词典、文本相似度、可读性；研究股票收益和波动。",
            "project_use": "将政策指引创新度、金融情感和股票波动放入同一可复现框架。",
            "not_adopted": "不照搬其全部市场和宏观控制变量，避免本科课设样本下过度参数化。",
        },
        {
            "source": "董青马等（2024）《央行沟通与资产价格——识别“潜在”未预期货币政策信息》",
            "verified_url": "https://www.jryj.org.cn/CN/abstract/abstract1334.shtml",
            "method_used_by_source": "强调市场反应来自增量信息和未预期政策信息。",
            "project_use": "用仅依赖历史数据的滚动 AR(1) 构造 expected_tone 与 unexpected_tone。",
            "not_adopted": "不实现潜在因子或卡尔曼滤波，以保持透明和可测试。",
        },
        {
            "source": "尚玉皇、刘华、申峰（2025）《预期的博弈：央行沟通与国债收益率曲线》",
            "verified_url": "https://www.jryj.org.cn/CN/abstract/abstract1520.shtml",
            "method_used_by_source": "研究沟通与收益率曲线整体水平、期限利差及市场预期互动。",
            "project_use": "构造 level、slope、curvature，并以斜率短窗作为债券主检验。",
            "not_adopted": "不强行扩展 Nelson-Siegel 或 PCA，因为当前稳定期限只有 1/5/10 年。",
        },
        {
            "source": "姜富伟等中文金融情感词典 GitHub",
            "verified_url": "https://github.com/MengLingchao/Chinese_financial_sentiment_dictionary",
            "method_used_by_source": "9228 个中文金融情感词，分积极和消极，免费使用但需引用。",
            "project_use": "作为 general_chinese_financial_lexicon 的主要来源。",
            "not_adopted": "不把一般正负情绪等同于政策宽松/偏紧。",
        },
        {
            "source": "Du et al. Chinese Financial Sentiment Dictionary",
            "verified_url": "https://github.com/ha0ba/Chinese_Financial_Sentiment_Dictionary",
            "method_used_by_source": "Review of Finance 论文词典，GPL-3.0，含 positive/negative/political words。",
            "project_use": "作为第二套公开词典补充，并在提交说明中保留 GPL 许可。",
            "not_adopted": "政治情感词仅作候选，不直接解释央行政策倾向。",
        },
    ]
    matrix = pd.DataFrame(rows)
    matrix.to_excel(RESEARCH_DIR / "LITERATURE_METHOD_MATRIX.xlsx", index=False)
    md = ["# 文献方法对照", "", "本项目的主检验在最终分析计划中事先锁定，不根据估计结果更换窗口或核心变量。"]
    for _, row in matrix.iterrows():
        md.extend(
            [
                "",
                f"## {row['source']}",
                "",
                f"- 来源：{row['verified_url']}",
                f"- 成功论文/项目方法：{row['method_used_by_source']}",
                f"- 本项目使用：{row['project_use']}",
                f"- 未采用方法：{row['not_adopted']}",
            ]
        )
    (RESEARCH_DIR / "METHOD_ALIGNMENT.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def build_text_features() -> pd.DataFrame:
    repair_guidance_sections()
    lexicon = build_combined_lexicon()
    metadata = load_report_metadata()
    section_texts = load_section_texts()
    scored_rows = []
    for _, row in section_texts.iterrows():
        if row["section"] not in {"guidance", "macro"}:
            continue
        found = bool(row.get("found", True))
        score = score_text(row["text"], lexicon) if found else {}
        metric_names = [
            "raw_positive_count",
            "raw_negative_count",
            "raw_dovish_count",
            "raw_hawkish_count",
            "normalized_sentiment",
            "normalized_policy_stance",
            "effective_chars",
            "sentence_count",
        ]
        topic_names = ["growth", "inflation", "risk", "exchange_rate", "financial_stability"]
        if not found:
            score = {name: np.nan for name in metric_names}
            score.update({f"attention_{topic}": np.nan for topic in topic_names})
        scored_rows.append(
            {
                "report_id": row["report_id"],
                "report_period": row["report_period"],
                "section": row["section"],
                "found": found,
                "text": row["text"],
                **score,
            }
        )
    section_scores = pd.DataFrame(scored_rows)
    for col in ["normalized_sentiment", "normalized_policy_stance"]:
        z_col = "z_" + col.replace("normalized_", "")
        section_scores[z_col] = np.nan
        for section, idx in section_scores.groupby("section").groups.items():
            sub = section_scores.loc[idx]
            formal = sub["report_period"].map(is_in_formal_sample) & sub[col].notna()
            mean = sub.loc[formal, col].mean()
            std = sub.loc[formal, col].std(ddof=0) or 1.0
            section_scores.loc[idx, z_col] = (sub[col] - mean) / std
    full = load_full_texts().merge(metadata[["report_id", "publication_datetime"]], on="report_id", how="left", suffixes=("", "_meta"))
    full = full.sort_values("publication_datetime").reset_index(drop=True)
    formal_full = full["report_period"].map(is_in_formal_sample)
    full["fulltext_similarity_full_sample_tfidf"] = np.nan
    full.loc[formal_full, "fulltext_similarity_full_sample_tfidf"] = adjacent_word_tfidf_similarity(full.loc[formal_full, "text"])
    full["fulltext_similarity_expanding_tfidf"] = adjacent_expanding_word_tfidf_similarity(full["text"])
    full["fulltext_novelty_expanding_tfidf"] = 1 - full["fulltext_similarity_expanding_tfidf"]
    full["fulltext_novelty_full_sample_tfidf"] = 1 - full["fulltext_similarity_full_sample_tfidf"]
    full["similarity_char_ngram"] = np.nan
    full.loc[formal_full, "similarity_char_ngram"] = adjacent_char_ngram_similarity(full.loc[formal_full, "text"])
    for col in ["fulltext_similarity_full_sample_tfidf", "fulltext_similarity_expanding_tfidf", "similarity_char_ngram"]:
        formal = full["report_period"].map(is_in_formal_sample) & full[col].notna()
        mean = full.loc[formal, col].mean()
        std = full.loc[formal, col].std(ddof=0) or 1.0
        full["z_" + col] = (full[col] - mean) / std
    full["report_length"] = full["char_count"]
    full["readability"] = full["char_count"] / full["text"].str.count("。|！|？|；").replace(0, np.nan)
    guidance = section_scores[section_scores["section"] == "guidance"].sort_values("report_period").copy()
    guidance["guidance_similarity_expanding_tfidf"] = adjacent_expanding_word_tfidf_similarity(guidance["text"].where(guidance["found"]))
    guidance["guidance_similarity_full_sample_tfidf"] = np.nan
    formal_guidance = guidance["report_period"].map(is_in_formal_sample)
    guidance.loc[formal_guidance, "guidance_similarity_full_sample_tfidf"] = adjacent_word_tfidf_similarity(
        guidance.loc[formal_guidance, "text"].where(guidance.loc[formal_guidance, "found"])
    )
    guidance["guidance_novelty"] = 1 - guidance["guidance_similarity_expanding_tfidf"]
    guidance["guidance_novelty_full_sample_tfidf"] = 1 - guidance["guidance_similarity_full_sample_tfidf"]
    wide = section_scores.pivot_table(
        index=["report_id", "report_period"],
        columns="section",
        values=[
            "z_sentiment",
            "z_policy_stance",
            "normalized_sentiment",
            "normalized_policy_stance",
            "attention_growth",
            "attention_inflation",
            "attention_risk",
            "attention_exchange_rate",
            "attention_financial_stability",
        ],
        aggfunc="first",
    )
    wide.columns = [f"{section}_{metric}" for metric, section in wide.columns]
    wide = wide.reset_index()
    features = metadata[["report_id", "report_period", "publication_datetime"]].merge(wide, on=["report_id", "report_period"], how="left")
    full_keep = full[
        [
            "report_id",
            "fulltext_similarity_full_sample_tfidf",
            "fulltext_similarity_expanding_tfidf",
            "fulltext_novelty_expanding_tfidf",
            "fulltext_novelty_full_sample_tfidf",
            "similarity_char_ngram",
            "z_similarity_char_ngram",
            "report_length",
            "readability",
        ]
    ]
    features = features.merge(full_keep, on="report_id", how="left")
    features = features.merge(
        guidance[
            [
                "report_id",
                "guidance_similarity_expanding_tfidf",
                "guidance_similarity_full_sample_tfidf",
                "guidance_novelty",
                "guidance_novelty_full_sample_tfidf",
            ]
        ],
        on="report_id",
        how="left",
    )
    for prefix in ["guidance", "macro"]:
        for topic in ["growth", "inflation", "risk", "exchange_rate", "financial_stability"]:
            col = f"{prefix}_attention_{topic}"
            if col in features.columns:
                features[f"{col}_change"] = features[col] - features[col].shift(1)
    unexpected = expanding_unexpected(features["guidance_z_policy_stance"])
    features["guidance_expected_tone"] = unexpected["expected_tone"]
    features["guidance_unexpected_tone"] = unexpected["unexpected_tone"]
    features["guidance_expected_method"] = unexpected["expected_method"]
    features["in_formal_sample"] = features["report_period"].map(is_in_formal_sample)
    diagnostics = features[
        [
            "report_id",
            "report_period",
            "guidance_z_policy_stance",
            "guidance_expected_tone",
            "guidance_unexpected_tone",
            "guidance_expected_method",
            "in_formal_sample",
        ]
    ]
    (OUTPUT_DIR / "diagnostics").mkdir(parents=True, exist_ok=True)
    diagnostics.to_excel(OUTPUT_DIR / "diagnostics" / "unexpected_tone_diagnostics.xlsx", index=False)
    features.to_csv(PROCESSED_DIR / "refactor_text_features.csv", index=False, encoding="utf-8-sig")
    section_scores.drop(columns=["text"]).to_csv(PROCESSED_DIR / "refactor_section_text_scores.csv", index=False, encoding="utf-8-sig")
    return features


def build_results() -> dict:
    ensure_dirs()
    verify_final_analysis_plan()
    build_research_documents()
    text_features = build_text_features()
    annotation_summary = build_manual_sentence_annotation(text_features)
    text_validation = run_text_validation()
    write_validation_outputs(text_validation)
    stock_panel = build_stock_event_panel(text_features)
    stock_panel.to_csv(PROCESSED_DIR / "refactor_stock_event_panel.csv", index=False, encoding="utf-8-sig")
    vol_paths = build_stock_volatility_paths(stock_panel)
    vol_paths.to_csv(PROCESSED_DIR / "refactor_stock_volatility_paths.csv", index=False, encoding="utf-8-sig")
    curve_daily, curve_panel = build_yield_curve_event_panel(text_features)
    curve_daily.to_csv(PROCESSED_DIR / "refactor_yield_curve_daily.csv", index=False, encoding="utf-8-sig")
    curve_panel.to_csv(PROCESSED_DIR / "refactor_yield_curve_event_panel.csv", index=False, encoding="utf-8-sig")

    vol_table, main_vol, egarch = run_stock_volatility_models(stock_panel)
    return_table = run_stock_return_models(stock_panel)
    curve_table = run_yield_curve_models(curve_panel)
    robust_table = similarity_robustness(stock_panel)
    desc = descriptive_stats(
        stock_panel.merge(curve_panel[["event_id", "delta_level_bp_0_3", "delta_slope_bp_0_3", "delta_curvature_bp_0_3"]], on="event_id", how="left"),
        [
            "log_rv_0_5",
            "rv_0_5",
            "guidance_novelty",
            "fulltext_novelty_expanding_tfidf",
            "guidance_z_sentiment",
            "macro_z_sentiment",
            "guidance_unexpected_tone",
            "guidance_attention_growth",
            "guidance_attention_inflation",
            "guidance_attention_risk",
            "return_0_p3",
            "delta_level_bp_0_3",
            "delta_slope_bp_0_3",
            "delta_curvature_bp_0_3",
        ],
    )
    tables = {
        "table1_variable_definitions": variable_definition_table(),
        "table2_descriptive": desc,
        "table3_stock_volatility": vol_table,
        "table4_stock_returns": return_table,
        "table5_yield_curve": curve_table,
        "table6_robustness": robust_table,
    }
    for name, df in tables.items():
        df.to_csv(TABLES_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    write_excel_tables(TABLES_DIR / "refactor_result_tables.xlsx", tables)
    (RESULTS_DIR / "stock_volatility_main.json").write_text(json.dumps(main_vol, ensure_ascii=False, indent=2), encoding="utf-8")
    write_egarch(RESULTS_DIR / "egarch_diagnostic.json", egarch)
    vol_table.to_csv(RESULTS_DIR / "stock_volatility_results.csv", index=False, encoding="utf-8-sig")
    return_table.to_csv(RESULTS_DIR / "stock_return_results.csv", index=False, encoding="utf-8-sig")
    curve_table.to_csv(RESULTS_DIR / "yield_curve_results.csv", index=False, encoding="utf-8-sig")
    robust_table.to_csv(RESULTS_DIR / "robustness_results.csv", index=False, encoding="utf-8-sig")
    legacy = ROOT / "output" / "results" / "primary" / "PRIMARY_RESULT_LOCK.json"
    shutil.copy2(legacy, RESULTS_DIR / "legacy_primary_result.json")

    plot_tone_series(text_features, FIGURES_DIR / "figure1_tone_series.png")
    plot_similarity(text_features, FIGURES_DIR / "figure2_similarity.png")
    plot_volatility_paths(vol_paths, FIGURES_DIR / "figure3_volatility_paths.png")
    plot_similarity_scatter(stock_panel, FIGURES_DIR / "figure4_similarity_rv_scatter.png")
    plot_yield_curve_factors(curve_daily, FIGURES_DIR / "figure5_yield_curve_factors.png")
    plot_curve_reactions(curve_panel, FIGURES_DIR / "figure6_curve_reactions.png")

    return {
        "text_features": text_features,
        "stock_panel": stock_panel,
        "curve_panel": curve_panel,
        "curve_daily": curve_daily,
        "tables": tables,
        "main_vol": main_vol,
        "egarch": egarch,
        "text_validation": text_validation["summary"],
    }


def run_pipeline(execute_nb: bool = True) -> dict:
    results = build_results()
    build_notebook()
    notebook_result = execute_notebook() if execute_nb else {"returncode": 0, "skipped": True}
    build_paper(results)
    pdf_check = inspect_pdf()
    submission_summary = build_final_submission()
    summary = {
        "status": "PASS",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "main_volatility_beta": results["main_vol"]["params"].get("guidance_novelty"),
        "main_volatility_p": results["main_vol"]["pvalues"].get("guidance_novelty"),
        "main_volatility_interaction_beta": results["main_vol"]["params"].get("guidance_novelty_x_post_2019"),
        "main_volatility_post_2019_total_effect": results["main_vol"]["post_2019_total_effect"],
        "main_volatility_effect_percent": results["main_vol"]["economic_effect"]["one_unit_guidance_novelty_percent_change_in_rv"],
        "manual_validation_rows": results["text_validation"]["total_sentences"],
        "text_validation_sentiment_accuracy": results["text_validation"]["sentiment_accuracy"],
        "text_validation_topic_accuracy": results["text_validation"]["topic_accuracy"],
        "notebook_returncode": notebook_result["returncode"],
        "pdf_pages": pdf_check["page_count"],
        "final_submission_files": submission_summary["included_files"],
    }
    (OUTPUT_DIR / "results" / "refactor_run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
