# 中国货币政策报告文本特征与金融市场反应

本项目是一个可复现的本科课程研究，主题为中国人民银行货币政策执行报告的文本特征与金融市场反应。文本数据库覆盖 2006Q1 至 2026Q1，正式实证样本锁定为 2006Q1 至 2025Q4。研究重点包括：

1. 政策指引章节扩展 TF-IDF 创新度与股票市场事件后波动；
2. 政策指引和宏观章节金融情感与股票短期收益；
3. 未预期政策语调与国债收益率曲线水平、斜率和曲率。

## 环境

建议使用 Python 3.12。Windows 下可执行：

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

也可以参考 `environment.yml` 创建环境。

## 复现命令

使用本地固定数据完整重建结果、Notebook、论文和最终提交目录：

```bash
.venv\Scripts\python run_all.py --offline
```

运行测试：

```bash
.venv\Scripts\python -m pytest -q
```

单独执行 Notebook：

```bash
.venv\Scripts\jupyter-nbconvert --execute --to notebook --inplace notebooks/货币政策沟通与金融市场反应.ipynb --ExecutePreprocessor.timeout=420
```

`--refresh-data` 为兼容参数；默认保护既有原始数据，不覆盖 `data/raw/`。

## 目录

- `src/monetary_policy/`：正式业务代码，按数据、文本、事件、分析、图表和报告分层。
- `data/raw/`：本地原始数据，不默认进入公开提交包。
- `data/processed/`：可复现分析数据。
- `data/dictionaries/`：公开金融情感词典和 PBC 领域扩展词典。
- `research/`：文献矩阵、方法对照和锁定分析计划。
- `output/figures/`、`output/tables/`、`output/results/`：图表、表格和模型结果。
- `notebooks/货币政策沟通与金融市场反应.ipynb`：展示核心 Python 处理流程。
- `paper/课程论文_提交版.docx`、`paper/课程论文_提交版.pdf`：课程论文。
- `final_submission/`：面向教师提交的精简目录。
- `archive/legacy_v1/`：早期版本代码、测试、Notebook、论文和原结果归档，不进入公开提交包。

## 数据和许可

报告数据来自中国人民银行官网。股票、债券和政策操作数据保留来源登记、采集时间和哈希，见 `data/source_registry.csv` 与 `DATA_LICENSE_AND_REDISTRIBUTION.md`。公开金融情感词典包括姜富伟等中文金融情感词典和 Du et al. 中文金融情感词典；后者为 GPL-3.0，最终提交说明保留许可证文件和引用要求。

## 主要结果

当前主检验使用政策指引扩展 TF-IDF 创新度、2019 年后虚拟变量及其交互项解释报告发布后五日股票实际波动率；债券主检验使用未预期政策语调、2019 年后虚拟变量及其交互项解释收益率曲线斜率 `[0,+3]` 变化。股票收益和其他收益率曲线因子作为补充证据报告。

## 提交前事项

论文封面中的作者、学号和任课教师需要手工补齐。若课程平台要求提交原始市场数据，请先确认数据再分发许可。

## 文本分类实验性审计

`experiments/` 中保存一组不会改变冻结主模型的有限探索：

```bash
python experiments/text_pipeline_probe.py
python experiments/crossfit_tone_market_probe.py
```

实验确认旧验证流程曾复用标注模板中的过期自动分数；当前验证代码已改为使用最新词典重新计分，并单独报告“政策相关句的方向识别”。字符 TF-IDF + LinearSVC 在按报告分组的交叉验证中可作为情感和政策倾向的替代测量，但跨拟合政策语调并未稳定改善债券回归，因此不替换文本创新度主线。完整结论见 `EXPERIMENTAL_ROUTE_ASSESSMENT.md`。
