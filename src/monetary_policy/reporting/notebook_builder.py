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
            "main = egarch_x['main_model']\n"
            "print({k: main.get(k) for k in ['method','sample_scope','date_start','date_end','n_daily_observations','n_report_events','n_novelty_events','n_policy_action_days','converged','runtime_seconds']})\n"
            "print('parameters:', main.get('parameters'))\n"
            "print('formal LR:', {k: main.get(k) for k in ['formal_lr_statistic','formal_lr_df','formal_lr_p_value','conditional_variance_change_pct_per_1sd_novelty','conditional_volatility_change_pct_per_1sd_novelty']})\n"
            "display(pd.DataFrame(egarch_x['sensitivity']))\n"
            "print('D0_D1 collinearity:', egarch_x['conditional_model'].get('D0_D1_collinearity_diagnostics'))\n"
            "print('comparison:', egarch_x.get('comparison'))"
        ),
        nbf.v4.new_markdown_cell("## 9. 市场功效分析"),
        nbf.v4.new_code_cell("power = pd.read_csv(ROOT / 'output/diagnostics/market_power_analysis.csv')\ndisplay(power)"),
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
