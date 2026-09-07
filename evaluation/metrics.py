from __future__ import annotations

import re
from dataclasses import dataclass, asdict


@dataclass
class EvaluationScores:
    keyword_accuracy: float
    answer_relevance: float
    citation_score: float
    unknown_behavior: float
    retrieval_quality: float
    hallucination_risk: float

    def to_dict(self) -> dict:
        return asdict(self)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def keyword_coverage(answer: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    text = normalize(answer)
    hits = sum(1 for word in expected_keywords if normalize(word) in text)
    return hits / len(expected_keywords)


def relevance_score(answer: str, question: str) -> float:
    # Lightweight deterministic proxy; not a semantic judge.
    q_tokens = {x for x in re.findall(r"[\w\-]+", normalize(question)) if len(x) > 3}
    a_tokens = set(re.findall(r"[\w\-]+", normalize(answer)))
    if not q_tokens:
        return 1.0
    return min(1.0, len(q_tokens & a_tokens) / max(1, min(4, len(q_tokens))))


def citation_score(answer: str, grounded: bool) -> float:
    if not grounded:
        return 1.0
    return 1.0 if re.search(r"\[S\d+\]", answer) else 0.0


def unknown_behavior_score(answer: str, expected_behavior: str | None) -> float:
    if expected_behavior != "abstain":
        return 1.0
    text = normalize(answer)
    markers = [
        "cannot confirm", "do not have enough", "not enough reliable", "لا أملك", "لا يمكنني تأكيد", "غير مؤكدة"
    ]
    return 1.0 if any(m in text for m in markers) else 0.0


def retrieval_score(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    if not expected_ids:
        return 1.0
    return len(set(retrieved_ids) & set(expected_ids)) / len(set(expected_ids))


def hallucination_risk_score(
    answer: str,
    expected_behavior: str | None,
    grounded: bool,
    citation_ok: float,
) -> float:
    # 0 = low observed risk; 1 = high observed risk in this deterministic test.
    if expected_behavior == "abstain":
        return 0.0 if unknown_behavior_score(answer, expected_behavior) == 1.0 else 1.0
    if not grounded:
        return 0.7
    if citation_ok == 0.0:
        return 0.4
    return 0.0
