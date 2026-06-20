from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import nbformat as nbf

from ..paths import NOTEBOOK_DIR, ROOT


NOTEBOOK_PATH = NOTEBOOK_DIR / "货币政策沟通与金融市场反应.ipynb"


def build_notebook() -> None:
    cells = [
        nbf.v4.new_markdown_cell("# 中国货币政策报告文本特征与金融市场反应\n\n本 Notebook 展示锁定分析计划、正式样本、章节修复、文本创新度、事件窗口、股票波动、股票收益和收益率曲线的核心计算。"),
        nbf.v4.new_code_cell("from pathlib import Path\nimport json\nimport pandas as pd\nROOT = Path.cwd()\nwhile not (ROOT / 'configs/project.yml').exists() and ROOT.parent != ROOT:\n    ROOT = ROOT.parent\nimport sys\nsys.path.insert(0, str(ROOT))\nprint(ROOT)"),
        nbf.v4.new_markdown_cell("## 1. 锁定分析计划和正式样本"),
        nbf.v4.new_code_cell("from src.monetary_policy.sample import verify_final_analysis_plan, sample_bounds, is_in_formal_sample\nverify_final_analysis_plan()\nprint('formal sample:', sample_bounds())"),
        nbf.v4.new_markdown_cell("## 2. 数据来源和覆盖范围"),
        nbf.v4.new_code_cell("registry = pd.read_csv(ROOT / 'data/source_registry.csv')\nregistry[['dataset_name','source_organization','coverage_start','coverage_end','license_or_terms']].head()"),
        nbf.v4.new_code_cell("meta = pd.read_csv(ROOT / 'data/processed/pbc_report_metadata.csv')\nmeta['in_formal_sample'] = meta['report_period'].map(is_in_formal_sample)\nmeta.groupby('in_formal_sample').size()"),
        nbf.v4.new_markdown_cell("## 3. 原始 PDF 抽取文本样例"),
        nbf.v4.new_code_cell("from src.monetary_policy.data.pbc_reports import report_text_path\nsample_id = meta.loc[meta['in_formal_sample'], 'report_id'].iloc[-1]\nsample_path = report_text_path(sample_id)\nraw_text = sample_path.read_text(encoding='utf-8')\nraw_text[:800]"),
        nbf.v4.new_markdown_cell("## 4. 文本清洗和章节识别"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.text_cleaner import normalize_text, split_sentences\ncleaned = normalize_text(raw_text[:1200])\nprint(cleaned[:500])\nprint('sentences:', len(split_sentences(cleaned)))"),
        nbf.v4.new_markdown_cell("## 5. 早期政策指引章节修复"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.section_repair import repair_guidance_sections\nrepair_guidance_sections()\nrepair = pd.read_excel(ROOT / 'output/diagnostics/section_repair_report.xlsx')\nrepair"),
        nbf.v4.new_code_cell("sections = pd.read_csv(ROOT / 'data/processed/report_sections_repaired.csv')\nsections[(sections['report_id'].isin(['2006Q1','2006Q4','2007Q2','2007Q4'])) & (sections['section']=='guidance')][['report_id','found','char_count','local_path']]"),
        nbf.v4.new_markdown_cell("## 6. 中文分词和自定义政策短语"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.tokenizer import tokenize\nexample = '保持流动性合理充裕，不搞大水漫灌，强化逆周期调节和跨周期调节。'\ntokenize(example)"),
        nbf.v4.new_markdown_cell("## 7. 金融情感词典和 PBC 领域词典"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.lexicon import build_combined_lexicon, COMBINED_PATH\nlexicon = build_combined_lexicon()\nprint(len(lexicon.positive), len(lexicon.negative), len(lexicon.dovish), len(lexicon.hawkish))\npd.read_csv(COMBINED_PATH).head()"),
        nbf.v4.new_markdown_cell("## 8. 否定词和程度副词处理示例"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.sentiment import score_text\nfor s in ['加大支持实体经济力度。','不搞大水漫灌。','更加有力支持稳增长。']:\n    print(s, score_text(s, lexicon))"),
        nbf.v4.new_markdown_cell("## 9. 文本指标计算"),
        nbf.v4.new_code_cell("from src.monetary_policy.pipeline import build_text_features\nfeatures = build_text_features()\nfeatures[['report_id','guidance_z_sentiment','macro_z_sentiment','guidance_z_policy_stance','guidance_unexpected_tone']].tail()"),
        nbf.v4.new_markdown_cell("## 10. 扩展 TF-IDF 创新度"),
        nbf.v4.new_code_cell("features[['report_id','in_formal_sample','guidance_similarity_expanding_tfidf','guidance_novelty','fulltext_novelty_expanding_tfidf','similarity_char_ngram']].dropna(subset=['guidance_novelty']).tail()"),
        nbf.v4.new_markdown_cell("## 11. 主题关注和未预期语调"),
        nbf.v4.new_code_cell("features.loc[features['in_formal_sample'], ['publication_datetime','guidance_z_sentiment','macro_z_sentiment','guidance_z_policy_stance','guidance_attention_growth','guidance_attention_inflation','guidance_unexpected_tone']].describe()"),
        nbf.v4.new_markdown_cell("## 12. 人工标注完成后的文本验证"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.manual_validation import load_filled_annotations, has_filled_annotations\nprint('人工标注已完成:', has_filled_annotations())\nfilled = load_filled_annotations()\nprint('标注句子数:', len(filled))\nprint('标注人:', filled['reviewer'].unique())\nprint()\nprint('情感标签分布:')\nprint(filled['manual_sentiment_label'].value_counts())\nprint()\nprint('政策倾向标签分布:')\nprint(filled['manual_policy_stance_label'].value_counts())\nprint()\nprint('主题标签分布:')\nprint(filled['manual_topic_label'].value_counts())"),
        nbf.v4.new_code_cell("from src.monetary_policy.text.validation_report import run_text_validation\nvresult = run_text_validation()\nprint(f\"情感 Accuracy: {vresult['summary']['sentiment_accuracy']:.4f}\")\nprint(f\"情感 Macro-F1: {vresult['summary']['sentiment_macro_f1']:.4f}\")\nprint(f\"政策倾向 Accuracy: {vresult['summary']['stance_accuracy']:.4f}\")\nprint(f\"政策倾向 Macro-F1: {vresult['summary']['stance_macro_f1']:.4f}\")\nprint(f\"主题 Accuracy: {vresult['summary']['topic_accuracy']:.4f}\")\nprint(f\"主题 Macro-F1: {vresult['summary']['topic_macro_f1']:.4f}\")\nprint()\nprint('不一致句子总数:', vresult['summary']['disagreement_count'])\nprint('  情感不一致:', vresult['summary']['disagreement_sentiment_count'])\nprint('  政策倾向不一致:', vresult['summary']['disagreement_stance_count'])\nprint('  主题不一致:', vresult['summary']['disagreement_topic_count'])"),
        nbf.v4.new_markdown_cell("## 13. 股票数据清洗"),
        nbf.v4.new_code_cell("stock = pd.read_csv(ROOT / 'data/processed/csi300_daily.csv', parse_dates=['date'])\nstock[['date','close','simple_return','volatility_20d']].tail()"),
        nbf.v4.new_markdown_cell("## 14. 债券收益率曲线数据"),
        nbf.v4.new_code_cell("bond = pd.read_csv(ROOT / 'data/processed/government_bond_yields.csv', parse_dates=['date'])\nbond[['date','yield_1y','yield_5y','yield_10y','spread_10y_1y']].tail()"),
        nbf.v4.new_markdown_cell("## 15. 发布时间和交易日对齐"),
        nbf.v4.new_code_cell("events = pd.read_csv(ROOT / 'data/processed/event_calendar.csv')\nevents['in_formal_sample'] = events['report_period'].map(is_in_formal_sample)\nevents['action_nearby_core'] = events['action_nearby']\nevents['action_nearby_extended'] = events.get('action_nearby_extended', events['action_nearby'])\nevents.loc[events['in_formal_sample'], ['event_id','publication_datetime','bond_event_date','equity_event_date','action_nearby_core','action_nearby_extended']].tail()"),
        nbf.v4.new_markdown_cell("## 16. 修正后的窗口收益函数"),
        nbf.v4.new_code_cell("from src.monetary_policy.events.event_windows import window_return\nprices = pd.Series([100, 102, 105, 110, 121])\nprint('0 to +3:', window_return(prices, 1, 0, 3))\nprint('-1 to +1:', window_return(prices, 1, -1, 1))"),
        nbf.v4.new_markdown_cell("## 17. 事件面板"),
        nbf.v4.new_code_cell("from src.monetary_policy.events.event_panel import build_stock_event_panel, build_yield_curve_event_panel\nstock_panel = build_stock_event_panel(features)\ncurve_daily, curve_panel = build_yield_curve_event_panel(features)\nstock_panel[['event_id','return_0_p3','rv_0_5','log_rv_0_5','pre_event_volatility_20d']].tail()"),
        nbf.v4.new_markdown_cell("## 18. 描述性统计"),
        nbf.v4.new_code_cell("stock_panel[['log_rv_0_5','guidance_novelty','guidance_novelty_x_post_2019','return_0_p3','guidance_z_sentiment']].describe()"),
        nbf.v4.new_markdown_cell("## 19. 股票波动率主结果"),
        nbf.v4.new_code_cell("from src.monetary_policy.analysis.stock_volatility import run_stock_volatility_models\nvol_table, main_vol, egarch = run_stock_volatility_models(stock_panel)\nvol_table"),
        nbf.v4.new_code_cell("main_vol['params'], main_vol['pvalues'], main_vol['post_2019_total_effect'], main_vol['economic_effect']"),
        nbf.v4.new_markdown_cell("## 20. 股票收益结果"),
        nbf.v4.new_code_cell("from src.monetary_policy.analysis.stock_returns import run_stock_return_models\nreturn_table = run_stock_return_models(stock_panel)\nreturn_table.head(12)"),
        nbf.v4.new_markdown_cell("## 21. 收益率曲线水平、斜率和曲率"),
        nbf.v4.new_code_cell("curve_daily[['date','level','slope','curvature']].tail()"),
        nbf.v4.new_code_cell("from src.monetary_policy.analysis.yield_curve import run_yield_curve_models\nyield_table = run_yield_curve_models(curve_panel)\nyield_table"),
        nbf.v4.new_markdown_cell("## 22. 原债券规格对照"),
        nbf.v4.new_code_cell("legacy = json.loads((ROOT / 'output/results/legacy_primary_result.json').read_text(encoding='utf-8')) if (ROOT / 'output/results/legacy_primary_result.json').exists() else json.loads((ROOT / 'output/results/primary/PRIMARY_RESULT_LOCK.json').read_text(encoding='utf-8'))\nlegacy['n'], legacy['params']['guidance_tone_change'], legacy['pvalues']['guidance_tone_change']"),
        nbf.v4.new_markdown_cell("## 23. 稳健性检验和 Holm 校正"),
        nbf.v4.new_code_cell("from src.monetary_policy.analysis.robustness import similarity_robustness\nsimilarity_robustness(stock_panel)"),
        nbf.v4.new_markdown_cell("## 24. 图表源数据"),
        nbf.v4.new_code_cell("sorted([p.name for p in (ROOT / 'output/figures').glob('figure*.png')])"),
        nbf.v4.new_markdown_cell("## 25. 结论和局限\n\n文本创新度、股票收益和收益率曲线结果均由上述模块现场计算。解释时只讨论相关性，不把事件研究回归写成因果识别。\n\n### 文本验证结论\n\n人工标注已完成（标注人：罗允绩，240 句，涵盖政策指引和宏观章节）。验证结论如下：\n\n- **金融情感**：自动词典的句子级准确率为 26.25%，主要问题是过度预测 positive（157/184 人工标注 neutral 的句子被自动分类为 positive）。原因在于姜富伟等和 Du et al. 的中文金融情感词典面向文档级金融市场分析设计，直接用于句子级政策文本时会产生系统性正向偏误。文档级聚合后的标准化指标在回归中更为稳健。\n- **政策倾向**：自动词典的句子级准确率为 14.17%，hawkish 召回率为 0%。PBC 领域鹰鸽词典（v2 已扩展至 35+33 词）在句子级仍存在严重覆盖不足，原因是政策倾向常通过隐含、间接表达传递。文档级聚合可在一定程度上缓解这一问题。\n- **主题分类**：v2 主题词典扩展后准确率从 38.33% 提升至 58.75%，growth 召回率从 35.1% 提升至 62.3%，financial_stability 召回率从 0% 提升至 36.8%。但 risk 和 inflation 的召回率仍偏低。\n\n词典修订版本已保存在 `data/dictionaries/lexicon_versions/` 目录下，含 v1→v2 变更报告。"),
    ]
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
    nb["cells"] = cells
    NOTEBOOK_PATH.write_text(nbf.writes(nb), encoding="utf-8")


def execute_notebook() -> dict:
    cmd = [
        str(ROOT / ".venv" / "Scripts" / "jupyter-nbconvert.exe"),
        "--execute",
        "--to",
        "notebook",
        "--inplace",
        str(NOTEBOOK_PATH),
        "--ExecutePreprocessor.timeout=420",
    ]
    tmp = ROOT / ".ipython_nbconvert_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "profile_default").mkdir(parents=True, exist_ok=True)
    (tmp / "profile_default" / "ipython_config.py").write_text("c = get_config()\nc.HistoryManager.enabled = False\n", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = str(ROOT / ".venv" / "Scripts") + os.pathsep + env.get("PATH", "")
    env["JUPYTER_ALLOW_INSECURE_WRITES"] = "true"
    env["IPYTHONDIR"] = str(tmp)
    env["JUPYTER_RUNTIME_DIR"] = str(tmp / "runtime")
    (tmp / "runtime").mkdir(exist_ok=True)
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=600)
    result = {"returncode": proc.returncode, "stdout_tail": proc.stdout[-1000:], "stderr_tail": proc.stderr[-2000:]}
    (ROOT / "output" / "results" / "notebook_execution_refactor.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return result


# Final-route notebook builder.  The definitions below intentionally override
# the earlier expanded draft and keep all displayed numbers loaded from result
# files generated by the formal pipeline.


def build_notebook() -> None:
    cells = [
        nbf.v4.new_markdown_cell("# 中国货币政策文本课设最终复现 Notebook\n\n本 Notebook 展示固定路线下的数据处理、文本特征工程、分组交叉验证、金融事件研究、稳健性检验和提交包审计。所有数字均由代码读取正式结果文件。"),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n"
            "ROOT = Path.cwd()\n"
            "while not (ROOT / 'configs/project.yml').exists() and ROOT.parent != ROOT:\n"
            "    ROOT = ROOT.parent\n"
            "import sys\n"
            "sys.path.insert(0, str(ROOT))\n"
            "print(ROOT)"
        ),
        nbf.v4.new_markdown_cell("## 1. 锁定分析计划与正式样本"),
        nbf.v4.new_code_cell(
            "from src.monetary_policy.sample import verify_final_analysis_plan, sample_bounds, is_in_formal_sample\n"
            "verify_final_analysis_plan()\n"
            "features = pd.read_csv(ROOT / 'data/processed/refactor_text_features.csv')\n"
            "print('sample_bounds =', sample_bounds())\n"
            "print(features[['report_id','report_period','in_formal_sample']].tail())\n"
            "print('formal_n =', int(features['in_formal_sample'].sum()))"
        ),
        nbf.v4.new_markdown_cell("## 2. 数据来源、章节修复与可追溯性"),
        nbf.v4.new_code_cell(
            "registry = pd.read_csv(ROOT / 'data/source_registry.csv')\n"
            "display(registry[['dataset_name','source_organization','coverage_start','coverage_end','license_or_terms']])\n"
            "repair = pd.read_excel(ROOT / 'output/diagnostics/section_repair_report.xlsx')\n"
            "display(repair)"
        ),
        nbf.v4.new_markdown_cell("## 3. 当前词典实时重打分与人工标注验证"),
        nbf.v4.new_code_cell(
            "validation = json.loads((ROOT / 'output/results/text_model_evaluation.json').read_text(encoding='utf-8')) if (ROOT / 'output/results/text_model_evaluation.json').exists() else None\n"
            "metrics = pd.read_excel(ROOT / 'output/diagnostics/text_validation_metrics.xlsx', sheet_name='summary')\n"
            "display(metrics.T)"
        ),
        nbf.v4.new_markdown_cell("## 4. 字符 TF-IDF + LinearSVC 分组交叉验证"),
        nbf.v4.new_code_cell(
            "text_model = json.loads((ROOT / 'output/results/text_model_evaluation.json').read_text(encoding='utf-8'))\n"
            "rows = []\n"
            "for name, obj in text_model.items():\n"
            "    if isinstance(obj, dict) and 'accuracy' in obj:\n"
            "        rows.append({'task': name, 'n': obj.get('n'), 'groups': obj.get('n_groups'), 'accuracy': obj.get('accuracy'), 'macro_f1': obj.get('macro_f1')})\n"
            "display(pd.DataFrame(rows))"
        ),
        nbf.v4.new_markdown_cell("## 5. 学习曲线"),
        nbf.v4.new_code_cell(
            "lc = pd.read_excel(ROOT / 'output/tables/table_learning_curve_summary.xlsx')\n"
            "display(lc)\n"
            "display(lc.sort_values(['task','train_ratio']).groupby('task').tail(1))"
        ),
        nbf.v4.new_markdown_cell("## 6. 扩展窗口 TF-IDF 创新度与连续主题关注度"),
        nbf.v4.new_code_cell(
            "topic = pd.read_csv(ROOT / 'data/processed/continuous_topic_attention.csv')\n"
            "display(features[['report_id','guidance_similarity_expanding_tfidf','guidance_novelty','guidance_novelty_expanding_tfidf','fulltext_novelty_expanding_tfidf']].tail())\n"
            "display(topic.loc[topic['in_formal_sample'], [c for c in topic.columns if 'attention' in c]].describe().T)"
        ),
        nbf.v4.new_markdown_cell("## 7. 股票事件级核心模型"),
        nbf.v4.new_code_cell(
            "stock_panel = pd.read_csv(ROOT / 'data/processed/refactor_stock_event_panel.csv')\n"
            "stock_results = pd.read_csv(ROOT / 'output/results/stock_volatility_results.csv')\n"
            "main_vol = json.loads((ROOT / 'output/results/stock_volatility_main.json').read_text(encoding='utf-8'))\n"
            "display(stock_panel[['event_id','log_rv_0_5','guidance_novelty','pre_event_volatility_20d','action_nearby_core','post_2019']].tail())\n"
            "display(stock_results)\n"
            "print(main_vol['post_2019_total_effect'])"
        ),
        nbf.v4.new_markdown_cell("## 8. Student-t EGARCH-X 稳健性"),
        nbf.v4.new_code_cell(
            "egarch_x = json.loads((ROOT / 'output/results/daily_egarch_x_results.json').read_text(encoding='utf-8'))\n"
            "print('formal D0 full joint MLE')\n"
            "print({k: egarch_x['main_model'].get(k) for k in ['method','sample_scope','n_daily_observations','n_report_events','converged','runtime_seconds']})\n"
            "print('parameters:', egarch_x['main_model'].get('parameters'))\n"
            "print('fixed-nuisance diagnostics')\n"
            "display(pd.DataFrame(egarch_x['sensitivity']))\n"
            "print('comparison:', egarch_x.get('comparison'))"
        ),
        nbf.v4.new_markdown_cell("## 9. 市场功效分析"),
        nbf.v4.new_code_cell(
            "power = pd.read_csv(ROOT / 'output/diagnostics/market_power_analysis.csv')\n"
            "display(power)"
        ),
        nbf.v4.new_markdown_cell("## 10. 跨拟合政策语调与国债收益率曲线探索"),
        nbf.v4.new_code_cell(
            "bond = pd.read_csv(ROOT / 'output/results/cross_fitted_bond_exploration.csv')\n"
            "yield_results = pd.read_csv(ROOT / 'output/results/yield_curve_results.csv')\n"
            "display(yield_results)\n"
            "display(bond)"
        ),
        nbf.v4.new_markdown_cell("## 11. 图表、论文和提交包审计"),
        nbf.v4.new_code_cell(
            "summary = json.loads((ROOT / 'output/results/refactor_run_summary.json').read_text(encoding='utf-8')) if (ROOT / 'output/results/refactor_run_summary.json').exists() else {}\n"
            "figures = sorted(p.name for p in (ROOT / 'output/figures').glob('figure*.png'))\n"
            "manifest = pd.read_csv(ROOT / 'delivery/FINAL_SUBMISSION_MANIFEST.csv') if (ROOT / 'delivery/FINAL_SUBMISSION_MANIFEST.csv').exists() else pd.DataFrame()\n"
            "print(summary)\n"
            "print('figures:', figures)\n"
            "print('final_submission_files:', len(manifest))"
        ),
    ]
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
    nb["cells"] = cells
    NOTEBOOK_PATH.write_text(nbf.writes(nb), encoding="utf-8")


def execute_notebook() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--execute",
        "--to",
        "notebook",
        "--inplace",
        str(NOTEBOOK_PATH),
        "--ExecutePreprocessor.timeout=420",
    ]
    tmp = ROOT / ".ipython_nbconvert_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "profile_default").mkdir(parents=True, exist_ok=True)
    (tmp / "profile_default" / "ipython_config.py").write_text("c = get_config()\nc.HistoryManager.enabled = False\n", encoding="utf-8")
    env = os.environ.copy()
    env["JUPYTER_ALLOW_INSECURE_WRITES"] = "true"
    env["IPYTHONDIR"] = str(tmp)
    env["JUPYTER_RUNTIME_DIR"] = str(tmp / "runtime")
    (tmp / "runtime").mkdir(exist_ok=True)
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=600)
    result = {"returncode": proc.returncode, "stdout_tail": proc.stdout[-1000:], "stderr_tail": proc.stderr[-2000:]}
    (ROOT / "output" / "results" / "notebook_execution_refactor.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return result
