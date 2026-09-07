from rag.query_analyzer import analyze_query


def test_arabic_operations_definition_is_overview():
    a = analyze_query("ما هو طور Operations؟")
    assert a.intent == "overview"
    assert a.topic == "operations"


def test_english_operations_definition_is_overview():
    a = analyze_query("What is Operations mode?")
    assert a.intent == "overview"
    assert a.topic == "operations"


def test_map_question_is_not_overview():
    a = analyze_query("ما هي خرائط Operations؟")
    assert a.topic == "operations"
    assert a.intent != "overview"
