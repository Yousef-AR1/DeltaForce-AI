from __future__ import annotations

from dataclasses import dataclass

from config import settings
from rag.query_analyzer import QueryAnalysis
from rag.retriever import RankedHit


@dataclass
class ValidationResult:
    accepted: bool
    reason: str
    hits: list[RankedHit]


def _official_announced_future(hit: RankedHit) -> bool:
    item = hit.item
    tags = {str(t).lower() for t in item.get("tags", [])}
    return (
        hit.trust_weight >= 0.90
        and item.get("knowledge_type") == "official_fact"
        and (item.get("status") == "announced_future" or "official_announcement" in tags or "announced_future" in tags)
    )


def validate_context(hits: list[RankedHit], analysis: QueryAnalysis) -> ValidationResult:
    if not hits:
        return ValidationResult(False, "No evidence was retrieved.", [])

    # Future questions are allowed only when the retrieved evidence is an explicit official announcement.
    if analysis.freshness == "future_unknown":
        announced = [h for h in hits if _official_announced_future(h) and h.final_score >= settings.min_retrieval_score]
        if announced:
            return ValidationResult(True, "Officially announced future information was retrieved.", hits)
        return ValidationResult(False, "No trusted official announcement confirms the requested future information.", hits)

    best = hits[0].final_score
    if best < settings.min_retrieval_score:
        return ValidationResult(False, f"Best evidence score {best:.3f} is below threshold {settings.min_retrieval_score:.3f}.", hits)

    if analysis.intent == "factual":
        trusted = [h for h in hits if h.trust_weight >= 0.90 and h.item.get("knowledge_type") in {"official_fact", "historical"}]
        if not trusted:
            return ValidationResult(False, "No sufficiently trusted factual source was retrieved.", hits)

    return ValidationResult(True, "Evidence passed grounding checks.", hits)
