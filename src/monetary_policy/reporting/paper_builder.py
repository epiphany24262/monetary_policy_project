from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import fitz
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..paths import FIGURES_DIR, PAPER_DIR, ROOT, TABLES_DIR


DOCX_PATH = PAPER_DIR / "课程论文_提交版.docx"
PDF_PATH = PAPER_DIR / "课程论文_提交版.pdf"


def _template() -> Path:
    return ROOT / "references" / "journal_format" / "统计研究基本版式.docx"


def _clear_body(doc: Document) -> None:
    body = doc._element.body
    for child in list(body):
        if not child.tag.endswith("sectPr"):
            body.remove(child)


def _table_rows(df: pd.DataFrame, max_rows: int = 8) -> list[list[str]]:
    view = df.head(max_rows).copy()
    return [list(view.columns)] + [[f"{x:.4f}" if isinstance(x, float) else str(x) for x in row] for row in view.to_numpy()]


def _paper_sections(results: dict) -> list[tuple[str, str]]:
    main = results["main_vol"]
    beta = main["params"]["guidance_novelty"]
    pval = main["pvalues"]["guidance_novelty"]
    interaction = main["params"]["guidance_novelty_x_post_2019"]
    interaction_p = main["pvalues"]["guidance_novelty_x_post_2019"]
    total = main["post_2019_total_effect"]["estimate"]
    total_p = main["post_2019_total_effect"]["p_value"]
    effect = main["economic_effect"]["one_unit_guidance_novelty_percent_change_in_rv"]
    legacy = json.loads((ROOT / "output/results/legacy_primary_result.json").read_text(encoding="utf-8"))
    curve = results["tables"]["table5_yield_curve"]
    curve_main = curve[curve["model"] == "main_yield_curve"].iloc[0]
    return [
        ("题名", "中国货币政策报告文本特征与金融市场反应\n——基于 Python 文本量化、股票波动与国债收益率曲线的研究\n\n作者：____  学号：____  任课教师：____"),
        ("摘要", f"本文基于中国人民银行货币政策执行报告研究央行沟通与金融市场短期反应。文本数据库覆盖 2006Q1 至 2026Q1，正式实证样本事先锁定为 2006Q1 至 2025Q4，2026Q1 只保留在数据更新记录中，不进入描述统计、回归、图表和论文数值。研究采用政策指引章节扩展 TF-IDF 创新度、金融情感词典、PBC 领域政策词典和仅使用历史信息的未预期语调指标。股票主模型以报告发布后五个交易日实际波动率的对数为被解释变量，使用政策指引创新度、事件前 20 日波动率、核心政策操作邻近变量、2019 年后虚拟变量及其交互项。估计结果显示，政策指引创新度的早期样本系数为 {beta:.4f}，HC3 p 值为 {pval:.4f}，2019 年后交互项为 {interaction:.4f}，p 值为 {interaction_p:.4f}，2019 年后总效应为 {total:.4f}，p 值为 {total_p:.4f}。债券主模型使用未预期政策语调解释收益率曲线斜率 `[0,+3]` 变化，主系数为 {curve_main['beta']:.4f}，p 值为 {curve_main['p_value']:.4f}。本文保留原 1 年期债券对照规格的不显著结果，不根据显著性更换主窗口或主变量。研究结论限于短窗口相关关系，不作强因果解释。\n\n关键词：货币政策沟通；政策指引；文本创新度；股票波动；收益率曲线"),
        ("一、引言", "中央银行定期报告兼具信息披露、预期管理和政策解释功能。对于中国人民银行货币政策执行报告而言，市场参与者不只读取某一句表述是否偏宽松，也会比较本期报告与上一期报告之间的表达是否延续、是否新增风险判断、是否改变政策取向、是否把宏观压力转化为政策支持信号。季度报告的发布频率低于新闻发布会、公开市场操作和宏观数据，因此其市场反应通常不会表现为单一方向的收益跳跃；更合理的问题是，报告中新增信息的多寡是否改变市场对不确定性的定价，以及未预期政策语调是否影响期限结构。\n\n本文围绕两个主检验展开。第一，政策指引章节的扩展 TF-IDF 创新度是否与报告发布后股票市场实际波动率相关。所谓创新度，是在每一期报告发布时只使用历史报告建立文本向量空间，再计算本期与上一期政策指引章节的余弦相似度，并取一减相似度。这样处理可以避免把未来文本带入历史测度，也能让指标更接近投资者在报告发布时能够观察到的“新信息”。第二，未预期政策语调是否与国债收益率曲线斜率变化相关。债券市场对央行沟通的反应往往表现为期限利差调整，而非单一短端利率变化；斜率指标可以同时容纳短端政策预期和长端增长、通胀及期限溢价预期。\n\n研究的一个重要处理是样本边界。文本数据库已经整理到 2026Q1，但正式样本锁定在 2006Q1 至 2025Q4。这一安排使数据更新与实证口径分离：新增文本可以保留在数据库中，便于将来延伸；正式统计和回归只使用锁定样本，避免在论文成稿过程中因新增季度而改变样本。早期四份报告的政策指引章节在自动标题识别中存在缺失，本文根据正文标题别名进行修复，并保留修复报告。未能识别的章节不会进入标准化和未预期语调计算，防止缺失文本被误当作真实零值。"),
        ("二、文献综述与研究假设", "央行沟通研究通常关心两个问题：沟通文本包含什么信息，以及市场如何吸收这些信息。姜富伟、胡逸驰和黄楠（2021）基于中国人民银行货币政策执行报告，区分宏观经济信息和未来政策指引信息，使用金融情感、文本相似度和可读性研究股票市场反应。该研究说明，央行文本不是一个单一情绪变量，宏观判断和政策指引在经济含义上不同；同时，文本相似度适合刻画信息延续性和新信息强度。董青马、张皓越、马剑文和尚玉皇（2024）强调资产价格反应来自未预期信息，而不是文本水平本身。尚玉皇、刘华和申峰（2025）将央行沟通放入国债收益率曲线框架，提示研究者需要关注水平、斜率和曲率，而不能只看某一个期限。\n\n基于上述思路，本文提出三个假设。假设一：政策指引章节创新度越高，报告发布后的股票市场波动率越高。这一假设来自信息不确定性机制。政策指引越延续，市场对政策路径的再定价压力越小；政策指引越新，投资者需要重新评估货币政策取向、流动性环境和实体融资条件，短期价格波动可能上升。假设二：2019 年以后政策指引创新度与股票波动之间的关系可能改变。2019 年以后，疫情冲击、房地产调整、外部利率环境变化和国内政策框架变化交织出现，市场对央行报告的解读背景不同，因而需要显式报告交互项，而不是把全部样本压缩为一个平均系数。假设三：未预期政策语调会影响收益率曲线斜率。若政策语调的变化已经被市场提前预期，其发布日反应有限；只有相对于历史预测出现偏离的部分，才更可能对应期限利差变化。"),
        ("三、数据来源与样本处理", "报告文本来自中国人民银行官网货币政策执行报告栏目，市场数据包括沪深 300 指数日行情和中债国债收益率曲线。项目保留数据来源登记、采集时间、文件哈希和许可说明。正式研究只使用可以追溯到公开来源的数据，不使用无法核验的替代数值，也不在数据源失败时编造观测。股票数据用于计算短窗口收益、事件后实际波动率和事件前 20 日波动率；债券数据使用 1 年、5 年和 10 年国债收益率构造水平、斜率和曲率。\n\n事件日期以报告公开发布时间对齐交易日。若报告在交易时段后或非交易日发布，股票和债券事件日顺延到下一有效交易日。股票收益窗口统一由窗口结束日收盘价相对窗口开始日收盘价计算，避免把更早的基准日错误带入所有窗口。股票波动主指标 `RV_0_5` 为事件日到后五个交易日的日收益标准差年化，回归中取自然对数。债券窗口固定为 `[0,+1]`、`[0,+3]` 和 `[0,+5]`，主模型选择斜率 `[0,+3]` 作为冻结规格，水平和曲率作为补充结果。\n\n政策操作邻近变量采用两套口径。核心口径只记录事件日前后三个有效日内稳定可核验的降准或 LPR 操作，作为所有主模型控制变量；扩展口径可容纳更宽范围的政策新闻或操作，但只用于稳健性说明，不进入主检验。这样区分的原因是，央行报告发布附近往往伴随其他政策信息，如果不加控制，文本指标可能吸收部分离散政策操作的影响；但若把低置信度事件放入主模型，又会增加测量误差。本文因此把可核验性放在显著性之前。"),
        ("四、文本指标构建", "文本处理从 PDF 抽取的清洗文本开始，识别宏观经济章节和政策指引章节。政策指引章节承载未来政策取向、流动性管理、信贷投放、融资成本和风险防范等内容，宏观章节则更多描述经济增长、物价、外部环境和金融运行状态。两类章节分别计分，避免把“经济压力加大”这类宏观负面判断误读为政策收紧。对于 2006Q1、2006Q4、2007Q2 和 2007Q4 四份早期报告，自动标题规则未能完整识别政策指引章节，本文使用正文标题别名和最后一次正文匹配提取相应部分，并将修复结果写入诊断表。\n\n金融情感指标来自公开中文金融情感词典和 PBC 领域扩展词典。一般金融情感使用积极词与消极词差额，政策倾向使用宽松词与偏紧词差额，两者均按有效字符数标准化。句子级计分考虑否定词、程度副词和转折词，例如“不搞大水漫灌”不能简单视为宽松，而“更加有力支持实体经济”应比普通支持表述权重更高。主题关注度围绕增长、通胀、风险、汇率和金融稳定五个方向计数，用于描述央行关注重点变化。所有标准化统计只使用正式样本，缺失章节不进入均值、标准差、未预期语调和回归。\n\n政策指引创新度的主变量采用扩展 TF-IDF。具体做法是对政策指引章节分词，并加入“流动性合理充裕”“逆周期调节”“跨周期调节”“不搞大水漫灌”“降低融资成本”等自定义短语。对第 t 期报告，只用第 1 期至第 t 期已经出现的文本拟合 TF-IDF，再计算第 t 期与第 t-1 期的余弦相似度，创新度定义为 `1 - similarity`。2006Q1 作为基准期，没有上一期可比报告，因此创新度为空；正式样本 80 期中，创新度有效样本最多为 79 期。全文创新度、全样本 TF-IDF 创新度和字符 n-gram 创新度只作为稳健性指标，不能替代主变量。"),
        ("五、研究设计", "股票主模型为：`log_rv_0_5 = alpha + beta1 * guidance_novelty + beta2 * pre_event_volatility_20d + beta3 * action_nearby_core + beta4 * post_2019 + beta5 * guidance_novelty_x_post_2019 + error`。其中 `post_2019` 在 2019Q1 及以后取 1，交互项用于报告制度环境和市场背景变化后的边际效应。本文解释三个量：2006—2018 年的早期效应 `beta1`，2019 年后新增变化 `beta5`，以及 2019 年后的总效应 `beta1 + beta5`。估计使用 OLS 和 HC3 稳健标准误，并报告 Bootstrap 置信区间、置换检验、VIF 和条件数。若交互项或总效应不显著，结论必须如实表达为证据不足，而不是调换变量寻找显著性。\n\n债券主模型为：`delta_slope_bp_0_3 = alpha + beta1 * guidance_unexpected_tone + beta2 * action_nearby_core + beta3 * post_2019 + beta4 * guidance_unexpected_tone_x_post_2019 + error`。未预期政策语调由扩展窗口预测得到：对每一期报告，只使用此前已经发布的政策倾向序列估计 AR(1) 预测值，实际政策倾向减去预测值即为未预期语调。历史长度不足时，使用上一期值作为保守预测；若没有上一期，则该期未预期语调为空。这个设定牺牲了复杂性，但避免未来信息泄漏，适合本科课程项目的透明复现要求。\n\n股票收益模型和收益率曲线水平、曲率模型为补充分析。股票收益报告 `[0,+1]`、`[0,+3]`、`[-1,+1]` 和 `[-1,+3]` 四个窗口，解释变量包括政策指引金融情感、宏观章节金融情感、政策倾向和未预期语调。收益率曲线补充结果报告水平、斜率和曲率多个窗口，并保留原 1 年期 `[-1,+3]` 规格作为对照。所有表格采用同一回归函数生成，数值来自同一批中间数据，避免正文、表格和图形之间出现数字不一致。"),
        ("六、文本特征和市场变量描述", "正式样本共 80 期报告，政策指引创新度有效观测为 79 期。图 1 展示政策指引金融情感、宏观章节金融情感、政策倾向和主题关注度的时间变化。可以看到，宏观章节在经济下行、外部冲击和金融风险阶段更容易出现负面金融情感；政策指引章节则更多围绕流动性、信贷、融资成本和风险防范调整表述。两类章节的差异说明，宏观情绪和政策取向不能简单相加。宏观章节出现压力词，可能代表政策支持空间上升；政策指引章节出现审慎词，则可能代表防风险约束增强。\n\n图 2 展示政策指引创新度、全文创新度和字符 n-gram 创新度。扩展 TF-IDF 创新度在报告文本发生较大表述变化时上升，例如新增外部环境、房地产、疫情、汇率或金融稳定判断时，政策指引章节与上一期的距离会扩大。字符 n-gram 指标保留为对照，因为它对固定句式和格式变化更敏感；若主结论只在字符指标上出现，而不在分词后的政策指引指标上出现，解释力会较弱。本文选择政策指引扩展 TF-IDF 创新度作为主变量，是因为它既与政策沟通理论对应，又满足发布时点可获得性。\n\n市场变量方面，沪深 300 短窗口收益具有明显波动聚集，事件前 20 日波动率在控制变量中十分必要。若某一期报告恰好发布在市场高波动阶段，发布后波动率可能自然较高；只有控制事件前波动率后，政策指引创新度系数才更接近报告新增信息与市场重新定价之间的关系。债券收益率曲线水平、斜率和曲率的变化幅度通常小于股票波动指标，但它们对应更明确的利率预期含义。斜率变化为本文债券主检验，因为政策沟通可能同时影响短端政策预期和长端经济预期。"),
        ("七、股票波动主结果", f"股票主模型样本量为 {main['n']}。政策指引创新度在早期样本的系数为 {beta:.4f}，HC3 p 值为 {pval:.4f}；2019 年后交互项为 {interaction:.4f}，p 值为 {interaction_p:.4f}；2019 年后的总效应为 {total:.4f}，p 值为 {total_p:.4f}。按对数波动率解释，创新度增加 1 个单位对应事件后实际波动率变化约 {effect:.2f}%。由于创新度通常位于 0 到 1 之间，经济解释时应结合实际分布，而不宜把 1 个单位变化视为常见季度变化。图 3 给出高低创新度报告后的平均绝对收益路径，图 4 展示创新度与 `log(RV_0_5)` 的散点关系。\n\n主结果的阅读重点不是某个 p 值是否跨过 0.05，而是早期效应、交互项和总效应是否构成一致的经济叙事。若早期系数为正而交互项为负，说明 2019 年以后政策指引创新度与股票波动之间的关系弱化或反向；若交互项为正，则说明后期市场对政策指引新信息更敏感。本文同时报告 Bootstrap 区间和置换检验，是为了降低小样本下单一稳健标准误的偶然性。季度报告样本最多只有 80 期，任何结论都不应被写成高频公告研究那样的强反应。\n\n从机制上看，政策指引创新度影响波动率有两种可能渠道。第一是信息更新渠道：新增政策取向、风险判断或流动性安排使投资者需要重估未来现金流折现率和风险溢价。第二是预期协调渠道：如果报告用更清晰的新表述解释政策框架，短期内也可能降低分歧，从而压低波动。因此，创新度系数的方向不能机械地解释为“新信息一定提高波动”，而要与 2019 年后交互项、事件前波动率和同期政策操作共同阅读。本文的任务是报告这种相关结构，而不是把央行报告等同于外生冲击。"),
        ("八、股票收益与债券曲线结果", f"股票收益结果用于补充说明文本语调是否对应短期方向性收益。政策指引金融情感、宏观章节金融情感、政策倾向和未预期语调分别进入 `[0,+1]`、`[0,+3]`、`[-1,+1]` 和 `[-1,+3]` 窗口。若政策指引情感为正而宏观情感为负，可能表示央行在承认经济压力的同时释放支持性政策信号；若两者同向，则可能代表基本面判断和政策取向共同改善。本文不把收益结果作为主结论，因为短窗口收益受同期宏观数据、全球市场、行业结构和风险偏好影响更强。\n\n债券主结果显示，未预期政策语调对收益率曲线斜率 `[0,+3]` 变化的系数为 {curve_main['beta']:.4f}，HC3 p 值为 {curve_main['p_value']:.4f}，2019 年后总效应为 {curve_main['post_2019_total_effect']:.4f}，总效应 p 值为 {curve_main['post_2019_total_p_value']:.4f}。斜率因子的含义是 10 年期收益率相对 1 年期收益率的变化。若未预期宽松语调降低短端利率预期而长端变化较小，斜率可能上升；若宽松语调同时降低增长预期和期限溢价，斜率也可能下降。因此，斜率结果需要与水平和曲率一起阅读。\n\n原 1 年期债券对照规格的系数为 {legacy['params']['guidance_tone_change']:.4f}，p 值为 {legacy['pvalues']['guidance_tone_change']:.4f}，方向为负但统计证据不足。本文保留这一结果，是因为季度报告不是单一政策公告，报告发布前市场已经通过公开市场操作、货币信贷数据、新闻发布会和宏观数据形成预期。对照规格不显著并不构成失败，反而提示央行报告文本的市场含义存在边界：文本信息更多体现预期管理和解释框架，短端利率在发布日窗口内未必出现稳定反应。"),
        ("九、稳健性、诊断与人工验证", "稳健性检验比较政策指引创新度、全文扩展 TF-IDF 创新度、全样本 TF-IDF 创新度和字符 n-gram 创新度，并对文本指标族进行 Holm 校正。主变量保持不变，其他指标只回答“结果是否依赖某一种文本表示”。如果稳健性指标方向不同，本文优先解释为文本维度差异，而不是据此替换主模型。分样本结果报告 2006—2018 年、2019—2025 年、疫情期间和非疫情期间，目的是揭示制度背景变化，而非挑选显著区间。\n\n诊断部分包括 VIF、条件数、Bootstrap、置换检验和 EGARCH。EGARCH 只用于描述日度收益的条件异方差诊断，文本变量进入的是 ARX 均值方程，而不是 EGARCH 方差方程。因此，EGARCH 输出不能被解释为“文本直接影响条件方差”的证据；真正的波动主检验仍是事件后实际波动率回归。这个区分很关键，因为若把均值方程中的事件变量误写成方差方程效应，会夸大模型含义。\n\n人工验证方面，本文已生成 240 条句子级抽样文件，政策指引和宏观章节基本均衡，且只包含正式样本。标签列保持空白，等待人工标注金融情感、政策倾向和主题类别。在标签完成前，本文不报告人工一致性或自动指标准确率。这样处理比程序自动填入“人工标签”更严谨，因为人工验证的价值在于独立判断，而不是复制词典规则。当前结论因此主要建立在公开词典、规则可复现和市场反应回归之上。"),
        ("十、结论", "本文在锁定样本和主模型的前提下，考察中国人民银行货币政策执行报告文本特征与金融市场短期反应。研究表明，政策指引章节的扩展 TF-IDF 创新度可以作为衡量央行沟通新增信息的核心指标，并与报告发布后股票市场实际波动率存在可检验关系；2019 年后交互项提示这种关系可能随市场背景和政策框架变化而改变。债券部分以未预期政策语调解释收益率曲线斜率变化，水平、曲率和原 1 年期规格作为补充证据。所有不显著结果均保留并解释，不因估计结果更换主窗口或主变量。\n\n本文的经验含义可以概括为三点。第一，央行季度报告的文本价值不只在于“宽松”或“偏紧”的方向判断，还在于政策指引相对于上一期是否出现新表达。市场面对高度延续的报告时，更多是在确认既有预期；面对创新度较高的报告时，则需要重新评估政策框架、风险权衡和流动性环境。第二，2019 年以后的交互项说明，同一类文本变化在不同市场背景下未必具有相同含义。疫情冲击、房地产调整、外部利率变化和国内稳增长政策叠加出现后，投资者对政策指引的吸收方式可能发生变化。第三，债券市场对央行沟通的反应不宜只看短端单一期限，收益率曲线斜率能够更好地反映短端政策预期与长端宏观预期之间的相对变化。\n\n本文的局限也较明确。第一，季度报告样本量有限，80 期正式样本不足以支持过度复杂的动态模型。第二，文本指标依赖 PDF 抽取、章节识别和词典规则，虽然早期缺失章节已经修复，但仍可能存在边界误差。第三，人工句子标签尚未完成，自动词典指标的外部有效性仍需后续人工复核。第四，事件窗口研究难以完全排除同期宏观消息和全球市场冲击，因此本文只讨论短窗口相关关系，不作严格因果识别。第五，政策操作邻近变量采用保守口径，能够降低误纳入风险，但也可能漏掉部分非标准化沟通信号。这些限制决定了本文结论应被理解为基于公开数据的经验证据，而不是完整的央行沟通定价模型。\n\n从数据治理角度看，本文坚持把文本数据库、正式样本和论文数值分开。2026Q1 已经进入文本整理范围，但不进入正式实证；早期政策指引章节经过规则修复后才参与计分；人工验证样本只提供待标注句子，不由程序填充人工判断。这些做法看似细碎，却直接关系到研究可信度。金融文本研究很容易因为样本边界、章节缺失、未来信息泄漏或标签来源不清而产生表面精确的结果。本文把这些环节显式记录下来，使读者能够追溯每一个指标来自哪类文本、进入了哪一张表、是否参与了主检验。\n\n本文结果的使用方式也需要保持克制。政策指引创新度较高，并不必然意味着市场会下跌或上涨，它首先表示报告相对上一期提供了更多不同表述；未预期语调也不是政策冲击本身，而是相对于历史可预测部分的偏离。投资者、教师或后续研究者若使用本文结果，应把它理解为央行沟通信息含量与短期市场波动之间的经验联系，而不是交易规则。尤其是在小样本和多重检验环境下，显著结果需要与经济机制、稳健性和样本背景同时判断，不显著结果同样提供边界信息。\n\n本文还提示，课程研究中的可复现不只是能再次运行程序，还包括变量口径、样本边界和文字解释能够被第三方读懂。若读者只看到最终系数，却无法判断章节如何抽取、窗口如何对齐、标准化是否排除了缺失值，研究就很难被验证。本文把这些选择放在同一套流程中，是为了让结果经得起逐项追问。\n\n尽管存在这些限制，本文仍提供了一个可复现的课程研究框架：从真实央行报告和公开市场数据出发，固定样本边界，锁定分析计划，构建发布时点可获得的文本指标，并用统一代码生成表格、图形、论文和提交包。后续研究可以在不改变主模型的前提下继续加入人工标签、高频公告、更多期限债券数据或更细政策操作分类，并检验新增样本是否改变目前的估计方向。对课程研究而言，这种流程比单个显著系数更重要，因为它要求研究者同时处理数据合法性、变量定义、事件窗口、统计检验和文字表述的一致性。"),
        ("研究复核说明", "为便于课程复核，本文所有核心数字均来自同一套中间表和结果表。读者可以从文本特征、事件面板、回归表、图形源数据逐步核对，确认 2026Q1 未进入正式样本、四个早期政策指引章节已经修复、人工验证样本保持空白标签、EGARCH 仅作为诊断而非主证据。这样的复核路径可以减少口径误差，也能让不显著结果和显著结果接受同样的检查。"),
        ("参考文献", "姜富伟、胡逸驰、黄楠，2021：《央行货币政策报告文本信息、宏观经济与股票市场》，《金融研究》第6期。\n董青马、张皓越、马剑文、尚玉皇，2024：《央行沟通与资产价格——识别“潜在”未预期货币政策信息》，《金融研究》第6期。\n尚玉皇、刘华、申峰，2025：《预期的博弈：央行沟通与国债收益率曲线》，《金融研究》第9期。\nDu, Z., Huang, A. G., Wermers, R., & Wu, W. 2022. Language and domain specificity: A Chinese financial sentiment dictionary. Review of Finance, 26(3), 673-719.\nGürkaynak, R. S., Sack, B., & Swanson, E. 2005. Do actions speak louder than words? International Journal of Central Banking, 1(1), 55-93."),
        ("英文题目、摘要和关键词", "Textual Features of China's Monetary Policy Reports and Financial Market Responses: Evidence from Policy-Guidance Novelty, Stock Volatility, and the Government Bond Yield Curve\n\nAbstract: This paper studies how textual features in the People's Bank of China's Monetary Policy Implementation Reports relate to short-window financial market responses. The formal empirical sample is locked at 2006Q1-2025Q4, while 2026Q1 is retained only as an update record. The main stock-market model uses expanding TF-IDF novelty in the policy-guidance section, a post-2019 indicator, and their interaction to explain post-release realized volatility. The main bond-market model uses unexpected policy tone and its post-2019 interaction to explain the short-window change in the yield-curve slope. All insignificant benchmark results are retained and interpreted cautiously.\n\nKeywords: monetary policy communication; policy guidance; textual novelty; stock volatility; yield curve"),
    ]


def build_paper(results: dict) -> None:
    doc = Document(_template())
    _clear_body(doc)
    if "Normal" in doc.styles:
        doc.styles["Normal"].font.size = Pt(10.5)
    for title, text in _paper_sections(results):
        if title == "题名":
            p = doc.add_paragraph()
            p.style = doc.styles["Title"] if "Title" in doc.styles else doc.styles["Normal"]
            p.add_run(text)
            continue
        doc.add_heading(title, level=1)
        for para in text.split("\n\n"):
            doc.add_paragraph(para)
        figure_map = {
            "六、文本特征和市场变量描述": ["figure1_tone_series.png", "figure2_similarity.png"],
            "七、股票波动主结果": ["figure3_volatility_paths.png", "figure4_similarity_rv_scatter.png"],
            "八、股票收益与债券曲线结果": ["figure5_yield_curve_factors.png", "figure6_curve_reactions.png"],
        }
        for fig_name in figure_map.get(title, []):
            fig = FIGURES_DIR / fig_name
            if fig.exists():
                doc.add_picture(str(fig), width=Inches(5.8))
        if title == "四、研究设计":
            table = doc.add_table(rows=1, cols=3)
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text = "变量", "定义", "角色"
            for _, row in pd.read_csv(TABLES_DIR / "table1_variable_definitions.csv").head(8).iterrows():
                cells = table.add_row().cells
                cells[0].text = str(row["variable"])
                cells[1].text = str(row["definition"])
                cells[2].text = str(row["role"])
        if title == "七、股票波动主结果":
            for name in ["table2_descriptive", "table3_stock_volatility", "table4_stock_returns", "table5_yield_curve", "table6_robustness"]:
                df = pd.read_csv(TABLES_DIR / f"{name}.csv")
                table = doc.add_table(rows=1, cols=min(len(df.columns), 6))
                for i, col in enumerate(df.columns[:6]):
                    table.rows[0].cells[i].text = col
                for _, row in df.head(6).iterrows():
                    cells = table.add_row().cells
                    for i, col in enumerate(df.columns[:6]):
                        cells[i].text = f"{row[col]:.4f}" if isinstance(row[col], float) else str(row[col])
    doc.save(DOCX_PATH)
    _build_pdf(results)


def _font_name() -> str:
    for path in [Path("C:/Windows/Fonts/simsun.ttc"), Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]:
        if path.exists():
            pdfmetrics.registerFont(TTFont("CNFont", str(path)))
            return "CNFont"
    return "Helvetica"


def _build_pdf(results: dict) -> None:
    font = _font_name()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal_cn", parent=styles["Normal"], fontName=font, fontSize=9.5, leading=14, wordWrap="CJK")
    heading = ParagraphStyle("heading_cn", parent=styles["Heading1"], fontName=font, fontSize=14, leading=20, spaceBefore=10, spaceAfter=6, wordWrap="CJK")
    title = ParagraphStyle("title_cn", parent=styles["Title"], fontName=font, fontSize=17, leading=24, alignment=1, wordWrap="CJK")
    doc = SimpleDocTemplate(str(PDF_PATH), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2.2 * cm, bottomMargin=2.0 * cm)
    story = []
    for sec, text in _paper_sections(results):
        story.append(Paragraph(text.replace("\n", "<br/>") if sec == "题名" else sec, title if sec == "题名" else heading))
        if sec != "题名":
            for para in text.split("\n\n"):
                story.append(Paragraph(para.replace("\n", "<br/>"), normal))
                story.append(Spacer(1, 0.08 * cm))
        figure_map = {
            "六、文本特征和市场变量描述": ["figure1_tone_series.png", "figure2_similarity.png"],
            "七、股票波动主结果": ["figure3_volatility_paths.png", "figure4_similarity_rv_scatter.png"],
            "八、股票收益与债券曲线结果": ["figure5_yield_curve_factors.png", "figure6_curve_reactions.png"],
        }
        for fig_name in figure_map.get(sec, []):
            fig = FIGURES_DIR / fig_name
            if fig.exists():
                story.append(Image(str(fig), width=14 * cm, height=8.5 * cm))
        if sec == "四、研究设计":
            for table_name in ["table1_variable_definitions", "table2_descriptive"]:
                df = pd.read_csv(TABLES_DIR / f"{table_name}.csv").head(6)
                t = Table(_table_rows(df, max_rows=6), repeatRows=1)
                t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, "black")]))
                story.append(t)
                story.append(Spacer(1, 0.15 * cm))
        if sec == "八、股票收益与债券曲线结果":
            for table_name in ["table3_stock_volatility", "table4_stock_returns", "table5_yield_curve", "table6_robustness"]:
                df = pd.read_csv(TABLES_DIR / f"{table_name}.csv").head(6)
                t = Table(_table_rows(df.iloc[:, :6], max_rows=6), repeatRows=1)
                t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, "black")]))
                story.append(t)
                story.append(Spacer(1, 0.15 * cm))
    doc.build(story)


def inspect_pdf() -> dict:
    for old in (ROOT / "output").glob("pdf_pages_refactor_old_*"):
        shutil.rmtree(old, ignore_errors=True)
    previous = ROOT / "output" / "pdf_pages_refactor"
    if previous.exists():
        try:
            previous.rename(ROOT / "output" / f"pdf_pages_refactor_old_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        except OSError:
            pass
    out_dir = ROOT / "output" / f"pdf_pages_refactor_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7), alpha=False)
        img = out_dir / f"page_{i+1:03d}.png"
        pix.save(img)
        samples = bytes(pix.samples)
        nonwhite = any(channel < 245 for channel in samples[:: max(1, len(samples) // 5000)])
        pages.append({"page": i + 1, "text_chars": len(text), "png": str(img.relative_to(ROOT)), "nonblank": len(text) > 20 or nonwhite})
    result = {"page_count": len(doc), "all_pages_nonblank": all(p["nonblank"] for p in pages), "pages": pages}
    doc.close()
    (ROOT / "output" / "results" / "pdf_visual_check_refactor.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result["all_pages_nonblank"]:
        raise RuntimeError("PDF visual check failed")
    return result
