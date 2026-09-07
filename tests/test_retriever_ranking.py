from rag.retriever import DeltaForceRetriever


def test_scoring_query_prefers_scoring_evidence_lexically():
    scoring = {
        "title": "Operations tournament scoring system overview",
        "content": "A squad total is Kill Points plus Asset Points.",
        "tags": ["operations", "tournament", "scoring", "kill points", "asset points"],
        "category": "competitive_rules",
    }
    unrelated = {
        "title": "Tournament Operator access",
        "content": "Operators are unlocked on the tournament server.",
        "tags": ["operator", "access"],
        "category": "competitive_rules",
    }

    q = "Explain the Operations tournament scoring system."
    assert DeltaForceRetriever._lexical_score(q, scoring) > DeltaForceRetriever._lexical_score(q, unrelated)


def test_scoring_query_expansion_contains_point_concepts():
    expanded = DeltaForceRetriever._expand_query("Explain the Operations tournament scoring system.")
    assert "Kill Points" in expanded
    assert "Asset Points" in expanded
