# Phase 1 数据可行性审计

## 结论

Phase 1 原型选择 A 完整方案进入 Phase 2：PBC 官方报告 + 中债 1/5/10 年国债收益率 + 沪深300辅助股票样本 + PBC 官方政策操作清单。由于中债和第三方股票接口的再分发许可不能默认确认，最终公开提交包应优先包含处理后必要数据和来源登记；若课程要求提交原始数据，需保留许可说明。

## Gate 1 检查

- 报告 PDF 可提取：5/5 份已提取文本。
- 目标章节自动识别：指引章节 5/5，宏观章节 5/5。
- 债券数据单位：`akshare.bond_china_yield` 返回中债国债收益率曲线，原型列值如 1.8、2.3，确认为百分比收益率；基点差需乘以 100。
- 债券窗口完整：5/5 个原型事件含 [-1,+3] 债券相对日。
- 债券/股票日历分离：已分别生成 `bond_event_date` 与 `equity_event_date`；差异事件数 1。
- 主检验冻结：见 `research/PRIMARY_ANALYSIS_FREEZE.md` 和 `.sha256`。
- A/B/C 方案：选择 A；B 为债券/股票可靠覆盖期降级；C 仅在无法合法取得日频市场数据时启用。
- 编造数据风险：未发现需要编造数据才能继续的环节。

## 样本原型文件

- `data/interim/pbc_report_index.csv`
- `data/raw/pbc_reports/*.pdf`
- `data/raw/market/chinabond_yield_prototype.csv`
- `data/raw/market/csi300_prototype.csv`
- `data/prototypes/phase1_event_window_panel.csv`
- `data/prototypes/phase1_primary_window_delta.csv`

## 限制与 Phase 2 修复项

1. 政策操作清单当前仅为原型，不得用于正式主检验；Phase 2 必须从 PBC 官方公告全量整理并记录来源链接。
2. 股票指数原型来自第三方接口，Phase 2 需用官方指数页面或交易所月报抽样核验。
3. 中债数据可查询但再分发许可不默认确认，公开提交包要遵守许可说明。
4. 章节抽取规则已通过原型，但 Phase 2 必须将多年份变体写入 `configs/section_patterns.yml` 并测试。