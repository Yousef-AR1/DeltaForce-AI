from rag.query_analyzer import analyze_query


def test_arab_heroes_is_mena_esports_topic():
    a = analyze_query("من فاز ببطولة أبطال العرب؟")
    assert a.topic == "mena_esports"


def test_pharaoh_scrim_is_mena_esports_topic():
    a = analyze_query("من فاز بسكرم لعنة الفراعنة؟")
    assert a.topic == "mena_esports"


def test_first_anniversary_is_mena_esports_topic():
    a = analyze_query("من بطل بطولة العام الأول MENA x TURKEY؟")
    assert a.topic == "mena_esports"
