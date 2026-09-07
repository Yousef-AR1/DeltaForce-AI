from rag.context_validator import validate_context
from rag.query_analyzer import QueryAnalysis
from rag.retriever import RankedHit


def make_analysis():
    return QueryAnalysis("en", "factual", "current", None, ["official_fact"])


def test_rejects_low_score():
    hit = RankedHit(
        item={"knowledge_type": "official_fact"},
        semantic_score=0.2,
        lexical_score=0.0,
        trust_weight=1.0,
        freshness_weight=1.0,
        type_weight=1.0,
        final_score=0.2,
    )
    assert validate_context([hit], make_analysis()).accepted is False
