from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean

from evaluation.metrics import (
    EvaluationScores,
    citation_score,
    hallucination_risk_score,
    keyword_coverage,
    relevance_score,
    retrieval_score,
    unknown_behavior_score,
)
from rag.rag_engine import DeltaForceRAG
from config import settings

BASE_DIR = Path(__file__).resolve().parent


def run_evaluation(questions_path: Path | None = None) -> dict:
    questions_path = questions_path or BASE_DIR / "questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    rag = DeltaForceRAG()
    rows = []

    for q in questions:
        result = rag.ask(q["question"])
        answer = result.answer
        ids = [h.item.get("id", "") for h in result.hits]

        c_score = citation_score(answer, result.grounded)
        scores = EvaluationScores(
            keyword_accuracy=keyword_coverage(answer, q.get("expected_keywords", [])),
            answer_relevance=relevance_score(answer, q["question"]),
            citation_score=c_score,
            unknown_behavior=unknown_behavior_score(answer, q.get("expected_behavior")),
            retrieval_quality=retrieval_score(ids, q.get("expected_record_ids", [])),
            hallucination_risk=hallucination_risk_score(
                answer, q.get("expected_behavior"), result.grounded, c_score
            ),
        )
        rows.append(
            {
                "id": q["id"],
                "category": q["category"],
                "language": q["language"],
                "question": q["question"],
                "answer": answer,
                "grounded": result.grounded,
                "retrieved_ids": ids,
                **scores.to_dict(),
            }
        )

    metric_names = [
        "keyword_accuracy",
        "answer_relevance",
        "citation_score",
        "unknown_behavior",
        "retrieval_quality",
        "hallucination_risk",
    ]
    summary = {name: mean(row[name] for row in rows) for name in metric_names}
    summary["answer_quality"] = mean(
        [
            summary["keyword_accuracy"],
            summary["answer_relevance"],
            summary["citation_score"],
            summary["unknown_behavior"],
        ]
    )
    summary["accuracy"] = summary["keyword_accuracy"]
    summary["relevance"] = summary["answer_relevance"]
    summary["hallucination"] = summary["hallucination_risk"]

    output = {
        "model": settings.model_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question_count": len(rows),
        "summary": summary,
        "results": rows,
        "notes": "Metrics are deterministic project metrics. They are proxies, not a human gold-standard evaluation.",
    }

    out_dir = BASE_DIR / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_model = "".join(c if c.isalnum() or c in "-_" else "_" for c in settings.model_name)
    out_path = out_dir / f"evaluation_{safe_model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    report = run_evaluation()
    print(json.dumps(report["summary"], indent=2))
