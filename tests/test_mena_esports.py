from rag.query_analyzer import analyze_query


def test_mena_arabic_query_detects_mena_esports():
    a = analyze_query("من بطل مينا في Delta Force؟")
    assert a.topic == "mena_esports"
    assert a.freshness == "any"


def test_emea_query_detects_mena_esports():
    a = analyze_query("What are the EMEA Delta Force tournaments?")
    assert a.topic == "mena_esports"


def test_arab_tournament_query_detects_mena_esports():
    a = analyze_query("شو بطولات العرب في Delta Force؟")
    assert a.topic == "mena_esports"
