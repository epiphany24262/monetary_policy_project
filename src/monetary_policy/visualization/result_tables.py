from __future__ import annotations

import pandas as pd


def variable_definition_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("log_rv_0_5", "报告发布后 0 至 +5 个股票交易日实际波动率的对数", "核心被解释变量"),
            ("guidance_novelty", "政策指引章节仅使用历史信息扩展 TF-IDF 后的相邻报告创新度", "股票波动核心解释变量"),
            ("guidance_novelty_x_post_2019", "政策指引创新度与 2019 年后样本虚拟变量的交互项", "结构变化解释变量"),
            ("guidance_z_sentiment", "政策指引章节金融情感指数的 Z 标准化值", "股票收益解释变量"),
            ("macro_z_sentiment", "宏观章节金融情感指数的 Z 标准化值", "宏观信息对照"),
            ("guidance_unexpected_tone", "仅用历史数据滚动 AR(1) 预测后的指引政策倾向残差", "未预期语调"),
            ("guidance_unexpected_tone_x_post_2019", "未预期政策语调与 2019 年后样本虚拟变量的交互项", "债券主模型解释变量"),
            ("level", "1 年、5 年、10 年国债收益率均值", "收益率曲线水平"),
            ("slope", "10 年期收益率减 1 年期收益率", "收益率曲线斜率"),
            ("curvature", "2×5 年期收益率 − 1 年期收益率 − 10 年期收益率", "收益率曲线曲率"),
            ("action_nearby_core", "事件日前后三个有效日内是否存在稳定可核验的降准或 LPR 政策操作", "冻结控制变量"),
            ("action_nearby_extended", "更宽口径政策操作邻近变量，仅用于稳健性而非主检验", "稳健性变量"),
        ],
        columns=["variable", "definition", "role"],
    )


def write_excel_tables(path, tables: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, df in tables.items():
            df.to_excel(writer, sheet_name=sheet[:31], index=False)
