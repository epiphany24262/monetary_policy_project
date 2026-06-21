from src.monetary_policy.text.text_cleaner import normalize_text, split_sentences


def test_split_sentences_handles_chinese_punctuation():
    text = "保持流动性合理充裕。防止资金空转；稳增长！"
    sentences = split_sentences(normalize_text(text))
    assert len(sentences) == 3
    assert sentences[0].endswith("。")

