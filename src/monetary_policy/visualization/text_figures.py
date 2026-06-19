from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def set_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120


def plot_tone_series(features: pd.DataFrame, path) -> pd.DataFrame:
    set_style()
    df = features[
        [
            "report_id",
            "publication_datetime",
            "guidance_z_sentiment",
            "macro_z_sentiment",
            "guidance_z_policy_stance",
            "guidance_attention_growth",
            "guidance_attention_inflation",
            "guidance_attention_risk",
            "in_formal_sample",
        ]
    ].drop_duplicates()
    df = df[df["in_formal_sample"]].drop(columns=["in_formal_sample"])
    df.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot(pd.to_datetime(df["publication_datetime"]), df["guidance_z_sentiment"], label="政策指引金融情感", color="black")
    ax.plot(pd.to_datetime(df["publication_datetime"]), df["macro_z_sentiment"], label="宏观章节金融情感", color="gray", linestyle="--")
    ax.plot(pd.to_datetime(df["publication_datetime"]), df["guidance_z_policy_stance"], label="政策指引倾向", color="#4575b4", linewidth=1.2)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("图1 政策指引、宏观语调与政策倾向")
    ax.set_ylabel("Z 标准化指数")
    ax.legend(loc="upper left", fontsize=8)
    ax2 = ax.twinx()
    topic = df[["guidance_attention_growth", "guidance_attention_inflation", "guidance_attention_risk"]].mean(axis=1)
    ax2.plot(pd.to_datetime(df["publication_datetime"]), topic, label="指引主题关注均值", color="#a6611a", alpha=0.65)
    ax2.set_ylabel("主题词频/千字")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return df


def plot_similarity(features: pd.DataFrame, path) -> pd.DataFrame:
    set_style()
    df = features[
        [
            "report_id",
            "publication_datetime",
            "guidance_similarity_expanding_tfidf",
            "guidance_novelty",
            "fulltext_novelty_expanding_tfidf",
            "similarity_char_ngram",
            "in_formal_sample",
        ]
    ].drop_duplicates()
    df = df[df["in_formal_sample"]].drop(columns=["in_formal_sample"])
    df.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(pd.to_datetime(df["publication_datetime"]), df["guidance_novelty"], label="政策指引创新度（扩展 TF-IDF）", color="black")
    ax.plot(pd.to_datetime(df["publication_datetime"]), df["fulltext_novelty_expanding_tfidf"], label="全文创新度（扩展 TF-IDF）", color="gray", linestyle="--")
    ax.plot(pd.to_datetime(df["publication_datetime"]), 1 - df["similarity_char_ngram"], label="字符 n-gram 创新度", color="gray", linestyle=":")
    ax.set_title("图2 相邻报告文本创新度")
    ax.set_ylabel("1 - 余弦相似度")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return df
