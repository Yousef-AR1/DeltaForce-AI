from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm.lmstudio import EmptyModelResponseError, LMStudioClient
from rag.context_validator import validate_context
from rag.prompt import build_messages
from rag.query_analyzer import analyze_query
from rag.retriever import DeltaForceRetriever, RankedHit


@dataclass
class RagResponse:
    answer: str
    grounded: bool
    reason: str
    analysis: Any
    hits: list[RankedHit]
    generation_mode: str = "llm"


class DeltaForceRAG:
    def __init__(self) -> None:
        self.retriever = DeltaForceRetriever()
        self.llm = LMStudioClient()

    @staticmethod
    def _evidence_fallback(language: str, hits: list[RankedHit]) -> str:
        """Last-resort answer that stays grounded even if the local LLM fails."""
        selected = hits[:3]
        if language == "ar":
            lines = [
                "بحسب المعلومات الموثوقة المتوفرة في قاعدة المعرفة:",
                "",
            ]
        else:
            lines = [
                "Based on the trusted information available in the knowledge base:",
                "",
            ]

        for i, hit in enumerate(selected, start=1):
            item = hit.item
            title = item.get("title") or "Evidence"
            content = str(item.get("content") or "").strip()
            if len(content) > 900:
                content = content[:897].rstrip() + "..."
            lines.append(f"**[S{i}] {title}**")
            lines.append(content)
            lines.append("")

        if language == "ar":
            lines.append("المصادر: " + ", ".join(f"[S{i}]" for i in range(1, len(selected) + 1)))
        else:
            lines.append("Sources: " + ", ".join(f"[S{i}]" for i in range(1, len(selected) + 1)))
        return "\n".join(lines).strip()

    @staticmethod
    def _direct_assistant_response(intent: str, language: str) -> str:
        if language == "ar":
            if intent == "identity":
                return (
                    "أنا **DeltaForce AI**، مساعد ذكاء اصطناعي متخصص في **Delta Force والـEsports**. "
                    "تم تصميمي لأجيب عن معلومات اللعبة باستخدام نظام **RAG**، بحيث أبحث أولًا في قاعدة معرفة "
                    "موثقة ومنظمة بدل الاعتماد على ذاكرة الموديل فقط. أقدر أساعدك في الأطوار مثل Operations "
                    "وWarfare، الأسلحة والـOperators والخرائط، قوانين البطولات، تاريخ البطولات، وبشكل خاص "
                    "بطولات **Garena Delta Force MENA** الموجودة في قاعدة المعرفة."
                )
            if intent == "capabilities":
                return (
                    "أقدر أساعدك في معلومات **Delta Force** مثل الأطوار، جميع الأسلحة، الذخيرة، الـOperators، الخرائط، المركبات، الـBosses، الأنظمة، "
                    "Operations وWarfare، الاستراتيجيات، قوانين البطولات والـEsports، وتاريخ ونتائج بطولات "
                    "**Garena MENA** مثل Arab Heroes وMENA × TURKEY. وإذا كانت المعلومة غير موجودة أو غير مؤكدة، "
                    "المفروض أوضح لك ذلك بدل اختراع جواب."
                )
            return (
                "أهلًا! أنا **DeltaForce AI** 👋 "
                "اسألني عن Delta Force، Operations، Warfare، الأسلحة، الـOperators أو بطولات Garena MENA."
            )

        if intent == "identity":
            return (
                "I am **DeltaForce AI**, an AI assistant specialized in **Delta Force and esports**. "
                "I use a RAG-based knowledge system so game-specific answers are grounded in retrieved sources "
                "instead of relying only on the language model's memory. I can help with game modes, weapons, "
                "operators, maps, tournament rules, esports history, and Garena Delta Force MENA events."
            )
        if intent == "capabilities":
            return (
                "I can help with Delta Force modes, weapons, ammunition, operators, maps, vehicles, bosses, systems, Operations, Warfare, "
                "strategies, tournament rules, esports history, and Garena MENA tournaments such as Arab Heroes "
                "and MENA × TURKEY. If the knowledge base does not contain reliable information, I should say so "
                "instead of inventing an answer."
            )
        return (
            "Hello! I am **DeltaForce AI** 👋 Ask me about Delta Force, Operations, Warfare, weapons, "
            "operators, or Garena MENA esports."
        )

    def ask(self, question: str) -> RagResponse:
        analysis = analyze_query(question)

        if analysis.intent in {"identity", "capabilities", "greeting"}:
            answer = self._direct_assistant_response(analysis.intent, analysis.language)
            return RagResponse(
                answer=answer,
                grounded=True,
                reason="Direct assistant identity/small-talk response; RAG and LM Studio were not required.",
                analysis=analysis,
                hits=[],
                generation_mode="direct",
            )

        hits = self.retriever.retrieve(question, analysis)
        validation = validate_context(hits, analysis)

        if not validation.accepted:
            fallback = (
                "لا أملك معلومات موثوقة كافية في قاعدة المعرفة الحالية لتأكيد الإجابة. "
                "جرّب سؤالًا أكثر تحديدًا أو حدّث مصادر المعرفة."
                if analysis.language == "ar"
                else "I do not have enough reliable information in the current knowledge base to confirm the answer. Try a more specific question or update the knowledge sources."
            )
            return RagResponse(fallback, False, validation.reason, analysis, hits, "safe_abstention")

        messages = build_messages(question, analysis, validation.hits)
        try:
            answer = self.llm.chat(messages=messages)
            return RagResponse(answer, True, validation.reason, analysis, validation.hits, "llm")
        except EmptyModelResponseError as exc:
            fallback = self._evidence_fallback(analysis.language, validation.hits)
            return RagResponse(
                fallback,
                True,
                f"{validation.reason} Model generation fallback used: {exc}",
                analysis,
                validation.hits,
                "evidence_fallback",
            )
