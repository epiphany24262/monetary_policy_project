# 修订分析计划

冻结时间：2026-06-19T18:38:39

本计划在重构版全量结果重新计算前写入。重构原因来自已发表文献和明确代码错误，不根据新结果调参。

## 核心结果一：文本相似度与股票波动

`log(RV_0_5) = alpha + beta1 * z_similarity_word_tfidf + beta2 * pre_event_volatility_20d + beta3 * action_nearby + beta4 * linear_time_trend + error`。OLS 使用 HC3 标准误，并报告 Bootstrap 置信区间和置换检验。

## 核心结果二：政策指引语调与股票收益

报告 `return_0_1`、`return_0_3`、`return_m1_p1`、`return_m1_p3`，比较政策指引金融情感、宏观章节金融情感、政策倾向和未预期语调。

## 扩展结果：国债收益率曲线

构造 `level=(1Y+5Y+10Y)/3`、`slope=10Y-1Y`、`curvature=2*5Y-1Y-10Y`，窗口为 `[0,+1]`、`[0,+3]`、`[0,+5]`。原 1 年期 `[-1,+3]` 规格保留为对照。

## 禁止事项

- 不因显著性继续更换核心窗口或变量。
- 不删除初版不显著结果。
- 不把相关性写成因果。
