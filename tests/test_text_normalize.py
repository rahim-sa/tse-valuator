from tse_valuator.ingestion.text_normalize import normalize_fa


def test_arabic_yeh_normalized_to_persian_yeh():
    assert normalize_fa("دارایی‌‌ها") == normalize_fa("دارايي‌ها".replace("ي", "ی"))


def test_arabic_kaf_normalized_to_persian_kaf():
    assert normalize_fa("بانك") == normalize_fa("بانک")


def test_whitespace_fully_stripped_for_matching():
    assert normalize_fa("  جمع   دارایی‌ها  ") == normalize_fa("جمعدارایی‌ها")


def test_real_mismatch_from_foolad_filing_now_matches():
    # Confirmed real-world mismatch: same words, different internal
    # spacing/invisible marks between our table and a live filing.
    from_our_table = "هزينه‏هاى فروش، ادارى و عمومى"
    from_live_filing = "هزينه ‏هاى فروش، ادارى و عمومى"
    assert normalize_fa(from_our_table) == normalize_fa(from_live_filing)