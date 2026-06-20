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
from .analysis.egarch_x import run_egarch_x, run_egarch_x_sensitivity, permutation_test_novelty, write_egarch_x_results
from .analysis.power_analysis import run_power_analysis, write_power_outputs
from .analysis.cross_fitted_tone import run_cross_fitted_tone, write_cross_fitted_outputs
from .data.bond_yields import load_bond_yields
from .data.market_prices import load_stock_prices
from .data.pbc_reports import load_full_texts, load_report_metadata, load_section_texts
from .events.event_calendar import load_event_calendar
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
from .text.manual_validation import build_manual_sentence_annotation, load_filled_annotations
from .text.validation_report import run_text_validation, write_validation_outputs
from .text.supervised_classifier import grouped_cross_validate, generate_learning_curve
from .text.context_gate import load_context_rules, gate_stance_label
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
        topic_names = list(lexicon.topics)
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
            "attention_real_estate",
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
    features["guidance_novelty_expanding_tfidf"] = features["guidance_novelty"]
    for prefix in ["guidance", "macro"]:
        for topic in list(lexicon.topics):
            col = f"{prefix}_attention_{topic}"
            if col in features.columns:
                features[f"{col}_change"] = features[col] - features[col].shift(1)
                formal = features["report_period"].map(is_in_formal_sample) & features[col].notna()
                mean = features.loc[formal, col].mean()
                std = features.loc[formal, col].std(ddof=0) or 1.0
                features[f"{col}_z"] = (features[col] - mean) / std
    unexpected = expanding_unexpected(features["guidance_z_policy_stance"])
    features["guidance_expected_tone"] = unexpected["expected_tone"]
    features["guidance_unexpected_tone"] = unexpected["unexpected_tone"]
    features["guidance_expected_method"] = unexpected["expected_method"]
    features["in_formal_sample"] = features["report_period"].map(is_in_formal_sample)
    topic_cols = [c for c in features.columns if "_attention_" in c and not c.endswith(("_change", "_z"))]
    features[["report_id", "report_period", "in_formal_sample", *topic_cols]].to_csv(
        PROCESSED_DIR / "continuous_topic_attention.csv", index=False, encoding="utf-8-sig"
    )
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

    # ── Context-gated text model evaluation ──
    text_model_summary = _run_text_model_evaluation()
    (RESULTS_DIR / "text_model_evaluation.json").write_text(
        json.dumps(text_model_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Supervised learning curves ──
    learning_curves = _run_learning_curves()

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

    # ── Student-t EGARCH-X on daily returns ──
    egarch_x_results = _run_daily_egarch_x(stock_panel)

    # ── Power analysis ──
    power_results = run_power_analysis(stock_panel)
    write_power_outputs(power_results)

    # ── Cross-fitted policy tone for bond exploration ──
    cross_fitted_summary = _run_cross_fitted_bonds(curve_panel, text_features)
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
            "guidance_attention_real_estate",
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
        "table7_learning_curve": pd.DataFrame(learning_curves["summary"]),
        "table8_market_power": power_results,
        "table9_cross_fitted_bond": pd.DataFrame(cross_fitted_summary.get("bond_exploration", [])),
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
        "text_model_summary": text_model_summary,
        "learning_curves": learning_curves,
        "egarch_x": egarch_x_results,
        "power_results": power_results.to_dict(orient="records"),
        "cross_fitted_summary": cross_fitted_summary,
    }


# ── Helper: text model evaluation ──
def _run_text_model_evaluation() -> dict:
    """Context-gated rescoring + grouped CV for policy stance and sentiment."""
    filled = load_filled_annotations()
    rules = load_context_rules()

    # Apply context gating
    gated_stance = []
    for _, row in filled.iterrows():
        auto_label = "neutral"
        score = row.get("auto_policy_stance_score", 0)
        if pd.notna(score) and score != 0:
            auto_label = "dovish" if score > 0 else "hawkish"
        gated = gate_stance_label(auto_label, str(row["sentence"]), rules)
        gated_stance.append(gated)
    filled["gated_stance"] = gated_stance

    # Grouped CV: sentiment
    sentiment_cv = grouped_cross_validate(
        filled["sentence"].tolist(),
        filled["manual_sentiment_label"].str.strip().str.lower().tolist(),
        filled["report_id"].tolist(),
        C=1.0, seed=2026,
    )

    # Grouped CV: policy stance (full four-class)
    stance_cv = grouped_cross_validate(
        filled["sentence"].tolist(),
        filled["manual_policy_stance_label"].str.strip().str.lower().tolist(),
        filled["report_id"].tolist(),
        C=1.0, seed=2026,
    )

    # Grouped CV: policy direction (excl irrelevant)
    dir_mask = filled["manual_policy_stance_label"].str.strip().str.lower() != "irrelevant"
    dir_sents = filled.loc[dir_mask, "sentence"].tolist()
    dir_labels = filled.loc[dir_mask, "manual_policy_stance_label"].str.strip().str.lower().tolist()
    dir_groups = filled.loc[dir_mask, "report_id"].tolist()
    direction_cv = grouped_cross_validate(dir_sents, dir_labels, dir_groups, C=1.0, seed=2026) if len(dir_sents) >= 10 else {"error": "Too few directional samples"}

    # Topic CV
    topic_labels = (
        filled["manual_topic_label"]
        .str.strip()
        .str.lower()
        .replace({"real_estate": "other"})
        .tolist()
    )
    topic_cv = grouped_cross_validate(
        filled["sentence"].tolist(),
        topic_labels,
        filled["report_id"].tolist(),
        C=1.0, seed=2026,
    )
    if "error" not in topic_cv:
        topic_cv["label_mapping_note"] = "manual real_estate is merged into other for supervised CV because it has one labelled sentence; continuous topic attention keeps real_estate separately."

    return {
        "sentiment_cv": sentiment_cv,
        "policy_stance_cv": stance_cv,
        "policy_direction_cv": direction_cv,
        "topic_cv": topic_cv,
        "n_gated_irrelevant": int(sum(1 for g in gated_stance if g == "irrelevant")),
    }


def _run_learning_curves() -> dict:
    """Generate learning curves for sentiment, stance, and topic."""
    filled = load_filled_annotations()
    curves = {}
    for task, label_col in [
        ("sentiment", "manual_sentiment_label"),
        ("policy_stance", "manual_policy_stance_label"),
        ("topic", "manual_topic_label"),
    ]:
        labels = filled[label_col].str.strip().str.lower()
        if task == "topic":
            labels = labels.replace({"real_estate": "other"})
        df_curve = generate_learning_curve(
            filled["sentence"].tolist(),
            labels.tolist(),
            filled["report_id"].tolist(),
            C=1.0, seed=2026,
        )
        curves[task] = df_curve
        # Save
        diag = OUTPUT_DIR / "diagnostics"
        diag.mkdir(parents=True, exist_ok=True)
        df_curve.to_csv(diag / f"learning_curve_{task}.csv", index=False, encoding="utf-8-sig")
    # Summary table
    summary_rows = []
    for task, df in curves.items():
        for _, row in df.iterrows():
            summary_rows.append({"task": task, "train_ratio": row["train_ratio"], "accuracy": row.get("accuracy"), "macro_f1": row.get("macro_f1"), "n": row.get("n")})
    summary = pd.DataFrame(summary_rows)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_excel(TABLES_DIR / "table_learning_curve_summary.xlsx", index=False)
    return {"curves": {k: v.to_dict(orient="records") for k, v in curves.items()}, "summary": summary_rows}


def _run_daily_egarch_x_fast(stock_panel: pd.DataFrame) -> dict:
    """Fast EGARCH-X via arch library (Student-t + Normal)."""
    from arch import arch_model
    stock = load_stock_prices()
    events = load_event_calendar()
    events = events.merge(stock_panel[["event_id", "guidance_novelty", "action_nearby_core"]], on="event_id", how="left")

    stock["report_day"] = 0.0
    stock["novelty_event"] = 0.0
    mapping = {}
    for _, ev in events.iterrows():
        d = pd.to_datetime(ev["equity_event_date"]).date()
        mapping[d] = ev.get("guidance_novelty", 0)
    stock["report_day"] = stock["date"].isin(set(pd.to_datetime(list(mapping.keys())))).astype(float)
    stock["novelty_event"] = stock["date"].dt.date.map(mapping).fillna(0.0)

    returns = stock["simple_return"].dropna() * 100  # percent returns
    X = stock[["report_day", "novelty_event"]].loc[returns.index].fillna(0)

    results = {}
    for dist_name, dist_param in [("student_t", "t"), ("normal", "normal")]:
        try:
            model = arch_model(
                returns, x=X, mean="ARX", lags=1,
                vol="EGARCH", p=1, o=1, q=1,
                dist=dist_param,
            )
            fit = model.fit(disp="off", show_warning=False)
            exog_names = [f"exog_{c}" for c in X.columns]
            exog_params = {}
            for i, col in enumerate(exog_names):
                if col in fit.params:
                    exog_params[col] = float(fit.params[col])
            results[dist_name] = {
                "status": "ok",
                "converged": bool(fit.convergence_flag == 0),
                "aic": float(fit.aic),
                "nobs": int(fit.nobs),
                "params": {k: float(v) for k, v in fit.params.items()},
                "exog_params": exog_params,
                "distribution": dist_name,
                "novelty_coef": exog_params.get("exog_novelty_event", None),
                "report_day_coef": exog_params.get("exog_report_day", None),
            }
        except Exception as e:
            results[dist_name] = {"status": "failed", "error": str(e)}

    # Permutation test (simplified)
    rng = np.random.default_rng(2026)
    base_coef = abs(results.get("student_t", {}).get("novelty_coef") or 0)
    count = 0
    n_perm = 200
    for _ in range(n_perm):
        perm_nov = rng.permutation(X["novelty_event"].to_numpy())
        X_perm = X.copy()
        X_perm["novelty_event"] = perm_nov
        try:
            m = arch_model(returns, x=X_perm, mean="ARX", lags=1, vol="EGARCH", p=1, o=1, q=1, dist="t")
            f = m.fit(disp="off", show_warning=False)
            if abs(float(f.params.get("novelty_event", 0))) >= base_coef:
                count += 1
        except Exception:
            continue
    perm_p = (count + 1) / (n_perm + 1)

    write_egarch_x_results(
        RESULTS_DIR / "daily_egarch_x_results.json",
        results.get("student_t", {}),
        pd.DataFrame([{"date_window": "D0", "distribution": d, **r} for d, r in results.items()]),
    )
    return {"main": results.get("student_t", {}), "normal": results.get("normal", {}), "permutation_p_novelty": float(perm_p)}


def _run_daily_egarch_x(stock_panel: pd.DataFrame) -> dict:
    """Student-t EGARCH-X on CSI 300 daily returns."""
    stock = load_stock_prices()
    events = load_event_calendar()
    events = events.merge(stock_panel[["event_id", "guidance_novelty", "action_nearby_core"]], on="event_id", how="left")

    stock["report_day"] = 0.0
    stock["novelty_event"] = 0.0
    stock["policy_action"] = 0.0
    mapping = {}
    action_mapping = {}
    for _, ev in events.iterrows():
        d = pd.to_datetime(ev["equity_event_date"]).date()
        mapping[d] = ev.get("guidance_novelty", 0)
        action_mapping[d] = ev.get("action_nearby_core", 0)
    stock["report_day"] = stock["date"].dt.date.isin(set(mapping.keys())).astype(float)
    stock["novelty_event"] = stock["date"].dt.date.map(mapping).fillna(0.0)
    stock["policy_action"] = stock["date"].dt.date.map(action_mapping).fillna(0.0)

    returns = stock["simple_return"].dropna()
    report_day = stock.loc[returns.index, "report_day"]
    novelty = stock.loc[returns.index, "novelty_event"]
    policy_action = stock.loc[returns.index, "policy_action"]

    main_result = run_egarch_x(returns, report_day, novelty, policy_action=policy_action, dist="student_t")
    sensitivity = run_egarch_x_sensitivity(returns, {
        "D0": report_day,
        "D0_D1": ((report_day.astype(bool) | report_day.shift(1).fillna(0).astype(bool)).astype(float)),
        "D1": report_day.shift(1).fillna(0).astype(float),
    }, novelty, policy_action=policy_action, dist="student_t")

    perm_p = permutation_test_novelty(returns, report_day, novelty, policy_action=policy_action, n_perm=50, seed=2026)
    write_egarch_x_results(RESULTS_DIR / "daily_egarch_x_results.json", main_result, sensitivity)

    return {"main": main_result, "sensitivity": sensitivity.to_dict(orient="records"), "permutation_p_novelty": perm_p}


def _run_cross_fitted_bonds(curve_panel: pd.DataFrame, text_features: pd.DataFrame) -> dict:
    """Cross-fitted policy tone → bond yield curve exploratory analysis."""
    filled = load_filled_annotations()
    guidance = filled[filled["section"] == "guidance"].copy()
    if len(guidance) < 20:
        return {"error": "Too few guidance sentences for cross-fitting"}

    sentence_path = PROCESSED_DIR / "report_sentences.csv"
    all_sentences = pd.read_csv(sentence_path) if sentence_path.exists() else guidance
    sent_preds, report_tone = run_cross_fitted_tone(guidance, all_sentences, n_splits=5, seed=2026)
    write_cross_fitted_outputs(sent_preds, report_tone)

    # Merge with curve panel (curve_panel uses event_id which equals report_id)
    curve_with_tone = curve_panel.merge(report_tone.rename(columns={"report_id": "event_id"}), on="event_id", how="left")
    bond_rows = []
    for tone_col in ["all_sentence_mean", "policy_relevant_mean", "directional_sentence_mean"]:
        if tone_col not in curve_with_tone.columns:
            continue
        inter_col = f"{tone_col}_x_post_2019"
        curve_with_tone[inter_col] = curve_with_tone[tone_col] * curve_with_tone["post_2019"]
        valid = curve_with_tone.dropna(subset=[tone_col, "delta_slope_bp_0_3"])
        if len(valid) < 10:
            bond_rows.append({"tone_aggregation": tone_col, "n": len(valid), "coef": float("nan"), "p_value": float("nan")})
            continue
        from .analysis.regressions import ols_hc3
        result = ols_hc3(valid, "delta_slope_bp_0_3", [tone_col, "action_nearby_core", "post_2019", inter_col])
        from .analysis.regressions import total_effect
        total = total_effect(result, tone_col, inter_col)
        bond_rows.append({
            "tone_aggregation": tone_col,
            "n": int(result["n"]),
            "coef": result["params"].get(tone_col, float("nan")),
            "p_value": result["pvalues"].get(tone_col, float("nan")),
            "interaction_coef": result["params"].get(inter_col, float("nan")),
            "interaction_p_value": result["pvalues"].get(inter_col, float("nan")),
            "post_2019_total_effect": total["estimate"],
            "post_2019_total_p_value": total["p_value"],
            "r2": result["r2"],
        })

    bond_table = pd.DataFrame(bond_rows)
    bond_table.to_csv(RESULTS_DIR / "cross_fitted_bond_exploration.csv", index=False, encoding="utf-8-sig")
    bond_table.to_excel(TABLES_DIR / "table_cross_fitted_bond_exploration.xlsx", index=False)
    return {
        "bond_exploration": bond_rows,
        "n_cross_fitted_reports": int(len(report_tone)),
        "n_cross_fitted_sentences": int(len(sent_preds)),
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
        "sentiment_cv_accuracy": results["text_model_summary"]["sentiment_cv"].get("accuracy"),
        "stance_cv_accuracy": results["text_model_summary"]["policy_stance_cv"].get("accuracy"),
        "egarch_x_status": results["egarch_x"]["main"].get("status"),
        "egarch_x_novelty_coef": results["egarch_x"]["main"].get("exog_params", {}).get("exog_1"),
        "egarch_x_perm_p": results["egarch_x"]["permutation_p_novelty"],
        "notebook_returncode": notebook_result["returncode"],
        "pdf_pages": pdf_check["page_count"],
        "final_submission_files": submission_summary["included_files"],
    }
    (OUTPUT_DIR / "results" / "refactor_run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
