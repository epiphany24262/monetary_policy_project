# 文献方法对照

本项目的主检验在最终分析计划中事先锁定，不根据估计结果更换窗口或核心变量。

## 姜富伟、胡逸驰、黄楠（2021）《央行货币政策报告文本信息、宏观经济与股票市场》

- 来源：https://www.jryj.org.cn/CN/abstract/abstract897.shtml
- 成功论文/项目方法：区分宏观经济信息和未来政策指引信息；使用金融情感词典、文本相似度、可读性；研究股票收益和波动。
- 本项目使用：将政策指引创新度、金融情感和股票波动放入同一可复现框架。
- 未采用方法：不照搬其全部市场和宏观控制变量，避免本科课设样本下过度参数化。

## 董青马等（2024）《央行沟通与资产价格——识别“潜在”未预期货币政策信息》

- 来源：https://www.jryj.org.cn/CN/abstract/abstract1334.shtml
- 成功论文/项目方法：强调市场反应来自增量信息和未预期政策信息。
- 本项目使用：用仅依赖历史数据的滚动 AR(1) 构造 expected_tone 与 unexpected_tone。
- 未采用方法：不实现潜在因子或卡尔曼滤波，以保持透明和可测试。

## 尚玉皇、刘华、申峰（2025）《预期的博弈：央行沟通与国债收益率曲线》

- 来源：https://www.jryj.org.cn/CN/abstract/abstract1520.shtml
- 成功论文/项目方法：研究沟通与收益率曲线整体水平、期限利差及市场预期互动。
- 本项目使用：构造 level、slope、curvature，并以斜率短窗作为债券探索性基准规格。
- 未采用方法：不强行扩展 Nelson-Siegel 或 PCA，因为当前稳定期限只有 1/5/10 年。

## 姜富伟等中文金融情感词典 GitHub

- 来源：https://github.com/MengLingchao/Chinese_financial_sentiment_dictionary
- 成功论文/项目方法：9228 个中文金融情感词，分积极和消极，免费使用但需引用。
- 本项目使用：作为 general_chinese_financial_lexicon 的主要来源。
- 未采用方法：不把一般正负情绪等同于政策宽松/偏紧。

## Du et al. Chinese Financial Sentiment Dictionary

- 来源：https://github.com/ha0ba/Chinese_Financial_Sentiment_Dictionary
- 成功论文/项目方法：Review of Finance 论文词典，GPL-3.0，含 positive/negative/political words。
- 本项目使用：作为第二套公开词典补充，并在提交说明中保留 GPL 许可。
- 未采用方法：政治情感词仅作候选，不直接解释央行政策倾向。
