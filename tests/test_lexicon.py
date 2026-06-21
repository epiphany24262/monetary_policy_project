from src.monetary_policy.text.lexicon import build_combined_lexicon


def test_combined_lexicon_uses_public_financial_dictionary_and_pbc_terms():
    lexicon = build_combined_lexicon()
    assert len(lexicon.positive) > 3000
    assert len(lexicon.negative) > 5000
    assert "流动性合理充裕" in lexicon.dovish
    assert "不搞大水漫灌" in lexicon.hawkish

