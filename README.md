# 中国货币政策报告文本特征与金融市场反应

本项目是《面向经济和金融的 Python 编程》课程研究。研究使用中国人民银行季度货币政策执行报告、沪深300指数、国债收益率曲线和公开政策操作数据，考察政策指引文本创新度与金融市场短期反应之间的关系。

## 项目简介

核心检验使用政策指引章节的扩展窗口 TF-IDF 创新度解释报告发布后五个交易日股票实际波动率。日度稳健性采用 Student-t EGARCH-X 模型。文本测量通过人工句子标注、语境门控规则、字符 TF-IDF 与 LinearSVC 的按报告分组交叉验证进行验证。债券市场部分使用未预期政策语调和跨拟合监督语调考察国债收益率曲线变化，作为探索性扩展。

## 目录结构

- `configs/`：样本边界、路径和模型设定。
- `src/monetary_policy/`：数据处理、文本测量、事件研究、图表和论文生成代码。
- `scripts/`：辅助执行脚本。
- `tests/`：复现一致性测试。
- `notebooks/`：已执行的核心流程 Notebook。
- `data/processed/`：处理后文本特征、事件面板和市场数据。
- `data/validation/`：人工句子标注样本。
- `data/source_registry.csv`：数据来源、覆盖期和许可说明。
- `output/results/`、`output/tables/`、`output/figures/`：正式结果、表格和图形。
- `paper/`：课程论文 DOCX、PDF和论文数字、引用核对表。
- `delivery/`：提交包清单和压缩文件。

## 环境安装

建议使用 Python 3.12。Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

macOS/Linux：

```bash
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## 运行方法

使用本地固定数据重建结果、Notebook、论文和提交包：

```powershell
.\.venv\Scripts\python run_all.py --offline
```

运行测试：

```powershell
.\.venv\Scripts\python -m pytest -q
```

Notebook 可单独执行：

```powershell
.\.venv\Scripts\jupyter-nbconvert --execute --to notebook --inplace notebooks/货币政策沟通与金融市场反应.ipynb --ExecutePreprocessor.timeout=420
```

## 主要输出

- `paper/课程论文_提交版.docx`
- `paper/课程论文_提交版.pdf`
- `notebooks/货币政策沟通与金融市场反应.ipynb`
- `output/results/stock_volatility_main.json`
- `output/results/daily_egarch_x_results.json`
- `output/results/yield_curve_results.csv`
- `delivery/final_submission.zip`

## 数据来源说明

货币政策报告来自中国人民银行官网。股票指数、国债收益率和政策操作数据保留来源登记、采集时间和处理后文件哈希，见 `data/source_registry.csv` 与 `DATA_LICENSE_AND_REDISTRIBUTION.md`。若课程平台要求另行提交原始市场数据，应先确认数据源再分发许可。

## 复现注意事项

默认命令使用已生成的本地数据和正式估计结果。若需要重新估计计算量较大的日度 EGARCH-X 模型，可在确认环境依赖后使用 `--recompute-heavy`；若只需更新学习曲线、跨拟合语调和功效分析，可使用 `--recompute-text-diagnostics`。
