from __future__ import annotations

from config import settings
from rag.query_analyzer import QueryAnalysis
from rag.retriever import RankedHit


SYSTEM_PROMPT = """You are DeltaForce AI, a domain-specialized assistant for Delta Force and esports.

GROUNDING RULES:
1. For Delta Force-specific factual claims, use ONLY the evidence supplied in CONTEXT.
2. Never present recommendations, community opinions, or tournament-specific practices as official game facts.
3. Clearly distinguish Official Fact, Historical Information, Recommendation, Community Information, and System Policy.
4. Prefer current evidence for questions about the current game. Historical evidence must be labeled historical.
5. Do not invent weapon stats, operator abilities, maps, patch changes, esports rules, dates, or future content.
6. If the evidence is insufficient or contradictory, say that the available knowledge base cannot confirm the answer.
7. Cite factual statements with source labels like [S1], [S2]. Never invent a citation label.
8. Answer in the user's language unless explicitly asked otherwise.
9. Recommendations must be phrased as recommendations based on available evidence, not guaranteed best choices.
10. Be concise but useful.
11. Always produce visible final answer text. Do not return reasoning-only output.
12. For mode OVERVIEW questions (for example: "What is Operations?" or "ما هو طور Operations؟"),
    explain the mode itself before mentioning maps or narrow details. Prefer this order:
    - What the mode is
    - Core idea / gameplay loop
    - Squad or player count confirmed by evidence
    - Main objective and how to win/succeed
    - Risk/reward or death/extraction consequences when supported
    - Important unique mechanics
    - Short difference from the other major Delta Force modes if supported
    Do not use a list of maps as the definition of a mode.
13. For MENA/EMEA esports questions, distinguish region labels precisely:
    - MENA = Middle East and North Africa.
    - EMEA = Europe, Middle East and Africa.
    - A winner of an EMEA event is an EMEA champion, not automatically a MENA or Arab champion.
    - If a tournament result is still TBD or unverified in the supplied evidence, explicitly say so and never invent a winner.
"""


def build_messages(query: str, analysis: QueryAnalysis, hits: list[RankedHit]) -> list[dict[str, str]]:
    blocks: list[str] = []
    char_count = 0
    for i, hit in enumerate(hits, start=1):
        item = hit.item
        block = (
            f"[S{i}]\n"
            f"Title: {item.get('title')}\n"
            f"Type: {item.get('knowledge_type')}\n"
            f"Category: {item.get('category')}\n"
            f"Source: {item.get('source_name')}\n"
            f"Date: {item.get('source_date') or 'unknown'}\n"
            f"Season: {item.get('season') or 'not specified'}\n"
            f"Patch: {item.get('patch') or 'not specified'}\n"
            f"Current: {item.get('is_current')}\n"
            f"Content: {item.get('content')}\n"
        )
        if char_count + len(block) > settings.max_context_chars:
            break
        blocks.append(block)
        char_count += len(block)

    context = "\n---\n".join(blocks)
    user_prompt = f"""QUERY ANALYSIS
Language: {analysis.language}
Intent: {analysis.intent}
Freshness requirement: {analysis.freshness}

CONTEXT
{context}

USER QUESTION
{query}

Produce a grounded answer directly from the evidence. Start with the answer itself, not analysis or hidden reasoning.

If Intent is overview, answer the broad concept first. Do not let map records, event records, or one narrow mechanic dominate the answer when a mode-overview record is available.

End with a short 'Sources' section listing only the source labels you actually used."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
