from rag.query_analyzer import analyze_query


def test_arabic_who_are_you():
    a = analyze_query("انت مين؟")
    assert a.intent == "identity"
    assert a.topic == "assistant_identity"


def test_arabic_capabilities():
    a = analyze_query("شو بتقدر تعمل؟")
    assert a.intent == "capabilities"
    assert a.topic == "assistant_identity"


def test_english_who_are_you():
    a = analyze_query("Who are you?")
    assert a.intent == "identity"


def test_greeting():
    a = analyze_query("مرحبا")
    assert a.intent == "greeting"
