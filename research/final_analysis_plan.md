# FINAL_ANALYSIS_PLAN

冻结日期：2026-06-19

本文件是第二轮精修后的最终分析计划。它在重新计算第二轮全量结果前创建。流水线不得覆盖本文件；任何变量、窗口或主模型变化都必须导致 SHA256 校验失败并中止运行。

## 样本口径

- 文本数据库保留：`2006Q1—2026Q1`。
- 正式实证样本：`2006Q1—2025Q4`。
- `2026Q1` 仅作为未来更新数据，不进入描述统计、回归、分样本、图表和论文数字。
- 2006Q1 是相似度和创新度基准文档；正式相邻文本指标最大有效样本为 `2006Q2—2025Q4`。

## 主检验一：政策指引创新度与股票波动的时间变化

主文本变量：

```text
guidance_similarity_expanding_tfidf
guidance_novelty = 1 - guidance_similarity_expanding_tfidf
```

计算规则：

1. 只使用政策指引章节；
2. 第 `t` 期指标只使用第 `1` 至第 `t` 期文本拟合词汇和 IDF；
3. 禁止用后期文本决定早期 IDF；
4. 2006Q1 作为基准，创新度为空；
5. 缺失政策指引章节不进入相似度计算。

主因变量：

```text
log_rv_0_5
```

主模型：

```text
log_rv_0_5
= alpha
+ beta1 * guidance_novelty
+ beta2 * pre_event_volatility_20d
+ beta3 * action_nearby_core
+ beta4 * post_2019
+ beta5 * guidance_novelty_x_post_2019
+ error
```

主模型不加入线性时间趋势。稳健性模型可加入 `centered_time_trend`，并报告 VIF、条件数和系数变化。

解释：beta1 为 2006—2018 年创新度与股票波动的关系，beta5 为 2019 年后变化，beta1+beta5 为 2019 年后总效应（须报告联合检验和置信区间）。

## 高级稳健性：Student-t EGARCH-X 日度波动模型

高级稳健性检验使用完整连续沪深300日收益率序列。正式 D0 规格为 Student-t EGARCH-X，创新度、报告日和真实政策操作日进入条件方差方程。D+1、D0+D1 和置换检验作为日期敏感性与统计诊断，不替代事件级股票波动主检验。

## 探索性扩展：未预期政策语调与收益率曲线斜率

因变量：

```text
delta_slope_bp_0_3
slope = yield_10y - yield_1y
```

模型：

```text
delta_slope_bp_0_3
= alpha
+ beta1 * guidance_unexpected_tone
+ beta2 * action_nearby_core
+ beta3 * post_2019
+ beta4 * guidance_unexpected_tone_x_post_2019
+ error
```

同样报告早期效应、交互效应、2019 年后总效应、联合检验、HC3、Bootstrap 和置换检验。

## 结果层级

- 核心主检验：政策指引创新度与股票发布后五日实际波动率
- 高级稳健性：Student-t EGARCH-X 日度波动模型
- 探索性扩展：未预期政策语调与国债收益率曲线斜率
- 次要结果：delta_level_bp_0_3、delta_curvature_bp_0_3、股票收益窗口
- 辅助稳健性：全文 expanding TF-IDF、full-sample TF-IDF、字符 n-gram、加入 centered time trend
- 历史基准：guidance_tone_change → 1Y yield [-1,+3]
