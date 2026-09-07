from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any

from config import settings
from rag.query_analyzer import QueryAnalysis
from rag.vector_store import FaissVectorStore


@dataclass
class RankedHit:
    item: dict[str, Any]
    semantic_score: float
    lexical_score: float
    trust_weight: float
    freshness_weight: float
    type_weight: float
    final_score: float


class DeltaForceRetriever:
    """Hybrid local retriever: semantic FAISS search + domain-aware lexical re-ranking."""

    def __init__(self, store: FaissVectorStore | None = None) -> None:
        self.store = store or FaissVectorStore()

    def retrieve(self, query: str, analysis: QueryAnalysis) -> list[RankedHit]:
        expanded_query = self._expand_query(query)
        raw_hits = self.store.search(expanded_query, top_k=settings.top_k_candidates)
        ranked: list[RankedHit] = []

        for hit in raw_hits:
            item = hit.item
            semantic = max(0.0, min(1.0, hit.semantic_score))
            lexical = self._lexical_score(query, item)
            trust = float(item.get("trust_level", 0.5))
            freshness = self._freshness_weight(item, analysis)
            type_weight = 1.0 if item.get("knowledge_type") in analysis.preferred_types else 0.80

            governance = 0.70 + 0.18 * trust + 0.12 * freshness
            semantic_component = semantic * governance * type_weight
            final = min(1.0, semantic_component + settings.lexical_bonus_weight * lexical)

            # Intent-aware re-ranking. Definition/overview questions should return a mode overview,
            # not a random map, weapon, event, or narrow mechanic that merely contains the mode name.
            final = max(0.0, min(1.0, final + self._intent_adjustment(query, item, analysis)))
            final = max(0.0, min(1.0, final + self._topic_adjustment(item, analysis)))

            # Official announced future content should remain discoverable for future questions.
            if analysis.freshness == "future_unknown" and self._is_official_future_announcement(item):
                final = min(1.0, final + 0.18)

            ranked.append(RankedHit(item, semantic, lexical, trust, freshness, type_weight, final))

        ranked.sort(key=lambda x: x.final_score, reverse=True)
        return ranked[: settings.top_k_context]

    @staticmethod
    def _normalize_tokens(text: str) -> set[str]:
        tokens = set(re.findall(r"[a-z0-9][a-z0-9+./-]*|[\u0600-\u06FF]+", text.lower()))
        stop = {
            "the", "a", "an", "is", "are", "of", "in", "on", "for", "to", "and", "or",
            "what", "how", "explain", "system", "about", "please", "me", "does", "do",
            "ما", "هو", "هي", "في", "من", "على", "عن", "اشرح", "لي", "كيف", "شو", "ايش",
        }
        return {t for t in tokens if t not in stop and len(t) > 1}

    @classmethod
    def _expanded_terms(cls, query: str) -> set[str]:
        terms = cls._normalize_tokens(query)
        q = query.lower()
        groups = {
            "scoring": {"score", "scoring", "points", "point", "ranking", "kill", "asset"},
            "نقاط": {"نقاط", "قتل", "اصول", "أصول", "ترتيب", "score", "points"},
            "tournament": {"tournament", "competitive", "esports", "competition", "rules"},
            "بطولة": {"بطولة", "قوانين", "تنافسي", "tournament", "esports"},
            "operations": {"operations", "extraction", "extract", "عمليات", "استخراج"},
            "عمليات": {"operations", "extraction", "عمليات", "استخراج"},
            "warfare": {"warfare", "pvp", "وارفير", "حرب"},
            "سلاح": {"weapon", "firearm", "gun", "سلاح", "اسلحة", "أسلحة"},
            "weapon": {"weapon", "firearm", "gun", "سلاح", "اسلحة"},
            "operator": {"operator", "ability", "gadget", "عميل", "شخصية"},
            "عميل": {"operator", "ability", "gadget", "عميل", "شخصية"},
            "خريطة": {"map", "maps", "خريطة", "خرائط"},
            "map": {"map", "maps", "خريطة", "خرائط"},
            "ammo": {"ammo", "ammunition", "caliber", "ذخيرة", "طلقات"},
            "ذخيرة": {"ammo", "ammunition", "caliber", "ذخيرة", "طلقات"},
            "attachment": {"attachment", "gunsmith", "ملحق", "تعديل"},
            "ملحق": {"attachment", "gunsmith", "ملحق", "تعديل"},
            "mandelbrick": {"mandelbrick", "brick", "decode", "ماندلبريك"},
            "ماندلبريك": {"mandelbrick", "brick", "decode", "ماندلبريك"},
            "season": {"season", "patch", "update", "موسم", "تحديث", "باتش"},
            "موسم": {"season", "patch", "update", "موسم", "تحديث", "باتش"},
            "mena": {"mena", "emea", "middle", "east", "north", "africa", "turkey", "esports", "tournament", "champion", "qualifier"},
            "مينا": {"mena", "emea", "الشرق", "الأوسط", "شمال", "افريقيا", "أفريقيا", "تركيا", "بطولة", "بطل", "تصفيات"},
            "العرب": {"mena", "emea", "arab", "middle", "east", "north", "africa", "بطولة", "بطل"},
            "emea": {"emea", "mena", "europe", "middle", "east", "africa", "regional", "tournament"},
        }
        for trigger, additions in groups.items():
            if trigger in q or trigger in terms:
                terms.update(additions)
        return terms

    @classmethod
    def _lexical_score(cls, query: str, item: dict[str, Any]) -> float:
        q_terms = cls._expanded_terms(query)
        if not q_terms:
            return 0.0

        title_text = str(item.get("title", ""))
        tags_text = " ".join(item.get("tags", []))
        category_text = str(item.get("category", ""))
        content_text = str(item.get("content", ""))
        title = cls._normalize_tokens(title_text)
        tags = cls._normalize_tokens(tags_text)
        category = cls._normalize_tokens(category_text)
        content = cls._normalize_tokens(content_text)

        def coverage(tokens: set[str]) -> float:
            return len(q_terms & tokens) / max(1, len(q_terms)) if tokens else 0.0

        score = 0.42 * coverage(title) + 0.28 * coverage(tags) + 0.10 * coverage(category) + 0.20 * coverage(content)
        q = query.lower().strip()
        combined = f"{title_text} {tags_text} {content_text}".lower()

        # Strong exact entity bonus for names/codes such as M4A1, M7, N-Two, AZ3, SVCH.
        entity_tokens = [t for t in cls._normalize_tokens(query) if re.search(r"[a-z0-9]", t)]
        for token in entity_tokens:
            if len(token) >= 2 and re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", combined):
                score += 0.20

        # Exact phrase match is very useful for named maps, operators and weapons.
        normalized_query = " ".join(re.findall(r"[a-z0-9+./-]+", q))
        if len(normalized_query) >= 4 and normalized_query in combined:
            score += 0.25

        if any(k in q for k in ("scoring", "score", "نقاط", "النقاط")):
            if "kill point" in combined: score += 0.16
            if "asset point" in combined: score += 0.16
            if "tiebreak" in combined or "ranking" in combined: score += 0.06

        return min(1.0, score)

    @staticmethod
    def _expand_query(query: str) -> str:
        q = query.lower()
        additions: list[str] = []
        rules = [
            (("ما هو طور", "ماهو طور", "شو طور", "شو هو", "ما هو", "what is", "explain", "overview"),
             "mode overview definition core gameplay objective squad size players goal extraction loot risk reward"),
            (("scoring", "score", "points", "نقاط", "النقاط"), "Kill Points Asset Points ranking tiebreaker tournament scoring"),
            (("mandelbrick", "ماندلبريك"), "MandelBrick decode pickup reset tournament rules"),
            (("economy", "اقتصاد"), "Tekniq Alloy supply kill reward losing streak equipment purchase"),
            (("weapon", "gun", "firearm", "سلاح", "اسلحة", "أسلحة"), "weapon firearm category assault rifle battle rifle SMG sniper marksman shotgun pistol"),
            (("operator", "عميل", "شخصية"), "operator role ability gadget tactical gear trait"),
            (("map", "maps", "خريطة", "خرائط"), "Operations map Warfare map Zero Dam Layali Grove Brakkesh Space City Tide Prison AZ3"),
            (("ammo", "ammunition", "ذخيرة"), "ammo ammunition caliber penetration"),
            (("next season", "الموسم القادم", "موسم القادم", "reorientation"), "official announcement season launch Reorientation September 8 2026"),
            (("mena", "مينا", "emea", "العرب", "تركيا", "turkey", "بطولات مينا", "بطل مينا", "بطل العرب",
               "arab heroes", "أبطال العرب", "ليلة الرعب", "مقاتلي الصحراء", "لعنة الفراعنة", "بطولة العام الأول"),
             "MENA EMEA Garena Discord Arab Heroes Night Terror Desert Fighters Pharaoh Curse First Anniversary Turkey esports tournament championship qualifier winner Operations Warfare DFI RISE Series"),
        ]
        for triggers, text in rules:
            if any(t in q for t in triggers): additions.append(text)
        return query if not additions else f"{query}\nRelated Delta Force concepts: {' '.join(additions)}"


    @classmethod
    def _intent_adjustment(cls, query: str, item: dict[str, Any], analysis: QueryAnalysis) -> float:
        if analysis.intent != "overview":
            return 0.0

        title = str(item.get("title", "")).lower()
        category = str(item.get("category", "")).lower()
        tags = {str(t).lower() for t in item.get("tags", [])}
        content = str(item.get("content", "")).lower()
        combined = f"{title} {category} {' '.join(tags)} {content}"

        bonus = 0.0

        # Strongly favor canonical overview/definition records.
        if category == "game_mode_overview":
            bonus += 0.34
        if "overview" in tags or "definition" in tags or "شرح" in tags or "فكرة" in tags:
            bonus += 0.16
        if "overview" in title or title.startswith("شرح طور") or "فكرة اللعب" in title:
            bonus += 0.12

        # Favor the requested mode itself.
        topic_terms = {
            "operations": {"operations", "عمليات"},
            "warfare": {"warfare", "حرب"},
            "black_hawk_down": {"black hawk down", "بلاك هوك داون"},
        }
        for term in topic_terms.get(analysis.topic, set()):
            if term in combined:
                bonus += 0.08
                break

        # For broad "what is this mode?" questions, narrow detail records are noise.
        map_words = {"map", "maps", "خريطة", "خرائط"}
        narrow_categories = {"maps", "tournament_maps", "weapon", "weapons", "ammo", "attachments"}
        if category in narrow_categories or tags.intersection(map_words):
            bonus -= 0.34

        narrow_words = [
            "password", "daily", "loot ownership", "radiation mechanic",
            "tournament-exclusive", "decoding station", "insertion point",
        ]
        if any(w in combined for w in narrow_words):
            bonus -= 0.18

        return max(-0.55, min(0.55, bonus))


    @staticmethod
    def _topic_adjustment(item: dict[str, Any], analysis: QueryAnalysis) -> float:
        if analysis.topic != "mena_esports":
            return 0.0

        category = str(item.get("category", "")).lower()
        title = str(item.get("title", "")).lower()
        tags = {str(t).lower() for t in item.get("tags", [])}
        content = str(item.get("content", "")).lower()
        combined = f"{title} {content} {' '.join(tags)}"

        bonus = 0.0
        if category in {"mena_esports", "garena_mena_esports_archive"}:
            bonus += 0.36
        if any(x in combined for x in ("mena", "مينا", "emea", "middle east", "north africa", "تركيا", "turkey")):
            bonus += 0.18
        if any(x in combined for x in ("champion", "winner", "بطل", "فاز", "نتائج", "results", "qualifier", "تصفيات")):
            bonus += 0.07

        # Push unrelated game-data records down for regional esports questions.
        unrelated_categories = {
            "weapons", "weapon", "ammo", "attachments", "maps", "game_mode_overview",
            "operators", "items", "bosses", "vehicles"
        }
        if category in unrelated_categories:
            bonus -= 0.32

        return max(-0.45, min(0.55, bonus))

    @staticmethod
    def _is_official_future_announcement(item: dict[str, Any]) -> bool:
        tags = {str(t).lower() for t in item.get("tags", [])}
        return (
            float(item.get("trust_level", 0)) >= 0.9
            and item.get("knowledge_type") == "official_fact"
            and (item.get("status") == "announced_future" or "official_announcement" in tags or "announced_future" in tags)
        )

    @classmethod
    def _freshness_weight(cls, item: dict[str, Any], analysis: QueryAnalysis) -> float:
        if analysis.freshness == "any":
            return 1.0
        if analysis.freshness == "future_unknown":
            return 1.0 if cls._is_official_future_announcement(item) else 0.45
        is_current = bool(item.get("is_current", False))
        if analysis.freshness == "historical":
            return 1.0 if not is_current or item.get("knowledge_type") == "historical" else 0.72
        if is_current:
            return 1.0
        raw = item.get("source_date")
        if not raw: return 0.65
        try:
            item_date = datetime.strptime(raw, "%Y-%m-%d").date()
            age_days = max(0, (date.today() - item_date).days)
            return max(0.45, 1.0 - age_days / 1600.0)
        except ValueError:
            return 0.60
