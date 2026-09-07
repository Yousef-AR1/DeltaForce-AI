from rag.query_analyzer import analyze_query


def test_arabic_recommendation_detection():
    result = analyze_query("ما أفضل استراتيجية في Warfare؟")
    assert result.language == "ar"
    assert result.intent == "recommendation"


def test_historical_detection():
    result = analyze_query("What changed before 2026?")
    assert result.freshness == "historical"
