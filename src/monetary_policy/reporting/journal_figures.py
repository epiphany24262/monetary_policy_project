from __future__ import annotations

import re
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.text import Text

from ..paths import FIGURES_DIR, ROOT
from .journal_style import FIGURE_STYLE


@dataclass
class JournalFigures:
    figure1: str
    figure2: str
    figure3: str
    figure4: str


def write_journal_figures(results: dict) -> JournalFigures:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _set_journal_plot_style()
    fig1 = FIGURES_DIR / "journal_figure1_guidance_similarity_novelty.png"
    fig2 = FIGURES_DIR / "journal_figure2_stock_novelty_volatility.png"
    fig3 = FIGURES_DIR / "journal_figure3_market_power.png"
    fig4 = FIGURES_DIR / "journal_figure4_bond_curve_tone.png"
    _plot_guidance_similarity_novelty(results["text_features"], fig1)
    _plot_stock_novelty_volatility(results["stock_panel"], fig2)
    _plot_market_power(pd.DataFrame(results["power_results"]), fig3)
    _plot_bond_curve_tone(results["curve_daily"], results["curve_panel"], fig4)
    return JournalFigures(fig1.name, fig2.name, fig3.name, fig4.name)


def _set_journal_plot_style() -> None:
    candidates = [
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for candidate in candidates:
        try:
            prop = font_manager.FontProperties(fname=candidate)
            plt.rcParams["font.sans-serif"] = [prop.get_name(), "SimSun", "Microsoft YaHei", "DejaVu Sans"]
            break
        except Exception:
            continue
    else:
        plt.rcParams["font.sans-serif"] = ["SimSun", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["font.family"] = ["sans-serif"]
    plt.rcParams["font.size"] = FIGURE_STYLE["axis_font_pt"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["savefig.dpi"] = FIGURE_STYLE["dpi"]
    plt.rcParams["axes.edgecolor"] = "#000000"
    plt.rcParams["axes.linewidth"] = 0.6
    plt.rcParams["grid.color"] = "#D9D9D9"
    plt.rcParams["grid.linewidth"] = 0.4
    plt.rcParams["lines.linewidth"] = 0.9


def _figsize(single: bool = True) -> tuple[float, float]:
    if single:
        return FIGURE_STYLE["width_cm"] / 2.54, FIGURE_STYLE["height_cm"] / 2.54
    return FIGURE_STYLE["double_panel_width_cm"] / 2.54, FIGURE_STYLE["double_panel_height_cm"] / 2.54


def _assert_no_figure_caption(fig, path) -> None:
    bad = []
    for obj in fig.findobj(Text):
        text = obj.get_text().strip()
        if re.match(r"^图\s*\d+", text) or "政策指引创新度与股票实际波动率" in text:
            bad.append(text)
    if bad:
        raise RuntimeError(f"Figure {path} contains embedded caption text: {bad}")


def _save(fig, path) -> None:
    _assert_no_figure_caption(fig, path)
    fig.savefig(path, dpi=FIGURE_STYLE["dpi"], bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def _plot_guidance_similarity_novelty(features: pd.DataFrame, path) -> None:
    df = features.loc[
        features["in_formal_sample"],
        ["publication_datetime", "guidance_similarity_expanding_tfidf", "guidance_novelty"],
    ].dropna()
    df = df.sort_values("publication_datetime")
    df.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=_figsize(True))
    x = pd.to_datetime(df["publication_datetime"])
    ax.plot(x, df["guidance_similarity_expanding_tfidf"], color="#000000", label="相似度")
    ax.plot(x, df["guidance_novelty"], color="#6E6E6E", linestyle="--", label="创新度")
    ax.set_ylabel("指数值")
    ax.set_xlabel("报告发布时间")
    ax.grid(axis="y", alpha=0.7)
    ax.legend(frameon=False, loc="upper right", fontsize=FIGURE_STYLE["legend_font_pt"])
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    _save(fig, path)


def _plot_stock_novelty_volatility(panel: pd.DataFrame, path) -> None:
    df = panel[["guidance_novelty", "log_rv_0_5", "post_2019"]].dropna().copy()
    df.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=_figsize(True))
    pre = df[df["post_2019"].eq(0)]
    post = df[df["post_2019"].eq(1)]
    ax.scatter(pre["guidance_novelty"], pre["log_rv_0_5"], s=18, color="#000000", alpha=0.78, label="2019年前")
    ax.scatter(post["guidance_novelty"], post["log_rv_0_5"], s=20, facecolor="white", edgecolor="#4D4D4D", linewidth=0.8, label="2019年后")
    if len(df) >= 3:
        beta, intercept = np.polyfit(df["guidance_novelty"], df["log_rv_0_5"], 1)
        xs = np.linspace(df["guidance_novelty"].min(), df["guidance_novelty"].max(), 80)
        ax.plot(xs, intercept + beta * xs, color="#6E6E6E", linewidth=1.0, label="线性拟合")
    ax.set_xlabel("政策指引创新度")
    ax.set_ylabel("五日实际波动率对数")
    ax.grid(axis="y", alpha=0.65)
    ax.legend(frameon=False, loc="best", fontsize=FIGURE_STYLE["legend_font_pt"])
    fig.tight_layout()
    _save(fig, path)


def _plot_market_power(power: pd.DataFrame, path) -> None:
    df = power[["sample_size", "power", "min_detectable_effect"]].copy()
    df.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=_figsize(True))
    ax.plot(df["sample_size"], df["power"], color="#000000", marker="o", markersize=3.5, label="检验功效")
    ax.axhline(0.8, color="#777777", linestyle="--", linewidth=0.8, label="80%参照线")
    ax.set_xlabel("事件样本量")
    ax.set_ylabel("功效")
    ax.set_ylim(0.55, 1.0)
    ax.grid(axis="y", alpha=0.65)
    ax.legend(frameon=False, loc="lower right", fontsize=FIGURE_STYLE["legend_font_pt"])
    fig.tight_layout()
    _save(fig, path)


def _plot_bond_curve_tone(curve_daily: pd.DataFrame, curve_panel: pd.DataFrame, path) -> None:
    factors = curve_daily[["date", "level", "slope", "curvature"]].dropna().copy()
    factors["date"] = pd.to_datetime(factors["date"])
    panel = curve_panel.dropna(subset=["guidance_unexpected_tone", "delta_slope_bp_0_3", "post_2019"]).copy()
    panel["tone_group"] = pd.qcut(panel["guidance_unexpected_tone"], q=3, labels=["低", "中", "高"])
    panel["period_group"] = panel["post_2019"].map({0: "2006-2018", 1: "2019-2025"})
    grouped = (
        panel.groupby(["tone_group", "period_group"], observed=True)["delta_slope_bp_0_3"]
        .mean()
        .reset_index()
    )
    factors.to_csv(path.with_name(path.stem + "_panel_a.csv"), index=False, encoding="utf-8-sig")
    grouped.to_csv(path.with_name(path.stem + "_panel_b.csv"), index=False, encoding="utf-8-sig")
    fig, axes = plt.subplots(2, 1, figsize=_figsize(False), gridspec_kw={"height_ratios": [1.05, 0.95]})
    ax = axes[0]
    sample = factors.iloc[:: max(int(len(factors) / 300), 1)]
    ax.plot(sample["date"], sample["level"], color="#000000", label="水平")
    ax.plot(sample["date"], sample["slope"], color="#5E5E5E", linestyle="--", label="斜率")
    ax.plot(sample["date"], sample["curvature"], color="#9A9A9A", linestyle=":", label="曲率")
    ax.set_ylabel("百分点")
    ax.text(0.01, 0.90, "Panel A", transform=ax.transAxes, fontsize=8, fontweight="bold")
    ax.grid(axis="y", alpha=0.65)
    ax.legend(frameon=False, loc="upper right", ncol=3, fontsize=FIGURE_STYLE["legend_font_pt"])

    ax2 = axes[1]
    pivot = grouped.pivot(index="tone_group", columns="period_group", values="delta_slope_bp_0_3").reindex(["低", "中", "高"])
    x = np.arange(len(pivot))
    width = 0.32
    for idx, column in enumerate(pivot.columns):
        offset = (idx - (len(pivot.columns) - 1) / 2) * width
        face = "#000000" if idx == 0 else "white"
        edge = "#000000" if idx == 0 else "#4D4D4D"
        ax2.bar(x + offset, pivot[column], width=width, label=column, color=face, edgecolor=edge, linewidth=0.8)
    ax2.axhline(0, color="#000000", linewidth=0.6)
    ax2.set_xticks(x)
    ax2.set_xticklabels(["低未预期语调", "中间", "高未预期语调"])
    ax2.set_ylabel("斜率变化(bp)")
    ax2.text(0.01, 0.90, "Panel B", transform=ax2.transAxes, fontsize=8, fontweight="bold")
    ax2.legend(frameon=False, loc="best", fontsize=FIGURE_STYLE["legend_font_pt"])
    ax2.grid(axis="y", alpha=0.65)
    fig.tight_layout(h_pad=0.8)
    _save(fig, path)
