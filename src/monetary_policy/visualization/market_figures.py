from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from .text_figures import set_style


def plot_volatility_paths(paths: pd.DataFrame, path) -> pd.DataFrame:
    set_style()
    source = paths.groupby(["similarity_group", "relative_day"], as_index=False)["abs_return"].mean()
    source.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for group, df in source.groupby("similarity_group"):
        ax.plot(df["relative_day"], df["abs_return"] * 100, marker="o", label=group)
    ax.set_xlabel("相对交易日")
    ax.set_ylabel("平均绝对日收益率（%）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return source


def plot_similarity_scatter(panel: pd.DataFrame, path) -> pd.DataFrame:
    set_style()
    source = panel[["guidance_novelty", "log_rv_0_5", "rv_0_5", "post_2019"]].dropna()
    source.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    colors = source["post_2019"].map({0: "black", 1: "#333333"})
    ax.scatter(source["guidance_novelty"], source["log_rv_0_5"], color=colors, alpha=0.75)
    if len(source) >= 3:
        b, a = np.polyfit(source["guidance_novelty"], source["log_rv_0_5"], 1)
        xs = np.linspace(source["guidance_novelty"].min(), source["guidance_novelty"].max(), 80)
        ax.plot(xs, a + b * xs, color="gray", linewidth=2)
    ax.set_xlabel("政策指引创新度（扩展 TF-IDF）")
    ax.set_ylabel("log(RV_0_5)")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return source


def plot_yield_curve_factors(daily: pd.DataFrame, path) -> pd.DataFrame:
    set_style()
    source = daily[["date", "level", "slope", "curvature"]].copy()
    source.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(source["date"], source["level"], label="水平", color="black")
    ax.plot(source["date"], source["slope"], label="斜率", color="gray", linestyle="--")
    ax.plot(source["date"], source["curvature"], label="曲率", color="gray", linestyle=":")
    ax.set_ylabel("百分点")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return source


def plot_curve_reactions(panel: pd.DataFrame, path) -> pd.DataFrame:
    set_style()
    data = panel.copy()
    data = data.dropna(subset=["guidance_unexpected_tone", "delta_slope_bp_0_3", "post_2019"])
    data["tone_group"] = pd.qcut(data["guidance_unexpected_tone"], q=3, labels=["低未预期语调", "中间", "高未预期语调"])
    data["period_group"] = data["post_2019"].map({0: "2006-2018", 1: "2019-2025"})
    source = data.groupby(["period_group", "tone_group"], observed=True)[["delta_level_bp_0_3", "delta_slope_bp_0_3", "delta_curvature_bp_0_3"]].mean().reset_index()
    source.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    pivot = source.pivot(index="tone_group", columns="period_group", values="delta_slope_bp_0_3")
    x = np.arange(len(pivot))
    width = 0.36
    for i, col in enumerate(pivot.columns):
        ax.bar(x + (i - 0.5) * width, pivot[col], width=width, label=col)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_ylabel("斜率 [0,+3] 变化（bp）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return source
