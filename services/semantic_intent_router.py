from __future__ import annotations

from dataclasses import dataclass
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from rag.embeddings import embed_query, embed_texts


@dataclass
class RouteResult:
    intent: str
    canonical_query: str
    confidence: float
    method: str
    matched_example: str | None = None


class SemanticIntentRouter:
    """
    Hybrid Arabic/English intent router:
      1) Arabic normalization + dialect normalization
      2) High-confidence structural rules
      3) Multilingual semantic matching using the same embedding model as RAG
      4) Fuzzy-text fallback if the embedding model is unavailable

    The purpose is not to replace RAG. It only routes structured/direct questions
    that have deterministic catalog answers.
    """

    TIME_WORDS = {
        "الان", "حاليا", "هسا", "هسه", "هلق", "هلا", "الحين", "دحين",
        "دلوقتي", "دلوقت", "توا", "تو", "دابا", "دوك", "now", "currently",
        "current", "right now", "rn", "live",
    }
    SEASON_WORDS = {
        "سيزن", "سيزون", "season", "موسم", "الموسم", "السيزن",
    }

    DIALECT_REPLACEMENTS = {
        # Question words
        "شنو": "ما",
        "شنهي": "ما",
        "شن": "ما",
        "واش": "ما",
        "اش": "ما",
        "ايش": "ما",
        "وش": "ما",
        "شو": "ما",
        "شكو": "ما",
        # Where
        "وين": "اين",
        "فين": "اين",
        "منين": "من اين",
        # Want
        "بدي": "اريد",
        "عايز": "اريد",
        "عاوز": "اريد",
        "ابي": "اريد",
        "ابغى": "اريد",
        "نبغي": "اريد",
        # Current time
        "هسا": "الان",
        "هسه": "الان",
        "هلق": "الان",
        "هلأ": "الان",
        "الحين": "الان",
        "دحين": "الان",
        "دلوقتي": "الان",
        "دلوقت": "الان",
        "توا": "الان",
        "تو": "الان",
        "دابا": "الان",
        "دوك": "الان",
        # Common game vocabulary
        "سيزن": "موسم",
        "سيزون": "موسم",
        "المود": "الطور",
        "مود": "طور",
        "مابات": "خرائط",
        "ماب": "خريطة",
        "خرايط": "خرائط",
        "اوبريتورز": "شخصيات",
        "اوبراتور": "شخصية",
        "اوبريتور": "شخصية",
        "جوال": "موبايل",
        "تلفون": "موبايل",
        "تليفون": "موبايل",
        "هاتف": "موبايل",
        "بي سي": "pc",
        "بلايستيشن": "playstation",
        "بلاي ستيشن": "playstation",
        "اكس بوكس": "xbox",
        "اكس بوكس": "xbox",
        "جارينا": "garena",
        "جلوبال": "global",
    }

    # Canonical queries are deliberately phrased to activate the existing
    # deterministic catalog services.
    DIRECT_INTENTS = {
        "current_season",
        "mobile_release", "pc_release", "console_release",
        "versions_overview", "download_overview", "account_progression",
        "all_operators", "all_operations_maps", "all_warfare_maps",
        "all_modes", "all_vehicles", "all_bosses", "all_ammo",
        "all_attachments", "all_systems", "all_weapons",
        "all_lmg", "all_shotguns", "all_smg", "all_snipers",
        "all_marksman", "all_rifles", "all_pistols",
        "identity", "capabilities",
    }

    def __init__(
        self,
        examples_path: Path,
        semantic_threshold: float = 0.60,
        semantic_margin: float = 0.025,
        fuzzy_threshold: float = 0.78,
    ) -> None:
        self.examples_path = examples_path
        self.data = json.loads(examples_path.read_text(encoding="utf-8"))
        self.intents = self.data["intents"]
        self.semantic_threshold = semantic_threshold
        self.semantic_margin = semantic_margin
        self.fuzzy_threshold = fuzzy_threshold

        self._example_texts: list[str] = []
        self._example_intents: list[str] = []
        for intent, cfg in self.intents.items():
            for example in cfg["examples"]:
                self._example_texts.append(example)
                self._example_intents.append(intent)

        self._example_vectors: np.ndarray | None = None

    @staticmethod
    def detect_language(text: str) -> str:
        return "ar" if re.search(r"[\u0600-\u06FF]", text) else "en"

    @classmethod
    def normalize(cls, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("ـ", "")
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)

        # Arabic character normalization.
        text = (
            text.replace("أ", "ا")
                .replace("إ", "ا")
                .replace("آ", "ا")
                .replace("ى", "ي")
                .replace("ؤ", "و")
                .replace("ئ", "ي")
        )

        # Punctuation normalization.
        text = re.sub(r"[؟?!،,:;()\[\]{}\"'`~]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # Replace multi-word dialect forms first.
        for src in sorted(cls.DIALECT_REPLACEMENTS, key=len, reverse=True):
            dst = cls.DIALECT_REPLACEMENTS[src]
            pattern = rf"(?<!\w){re.escape(src)}(?!\w)"
            text = re.sub(pattern, dst, text)

        return re.sub(r"\s+", " ", text).strip()

    def _canonical(self, intent: str, language: str) -> str:
        key = "canonical_ar" if language == "ar" else "canonical_en"
        return self.intents[intent][key]

    def _rule_route(self, question: str, language: str) -> RouteResult | None:
        q = self.normalize(question)
        tokens = set(q.split())

        # Current season: captures "اي سيزن اللعبة الان؟", "وش السيزن الحين",
        # "what season are we on rn", etc.
        has_season = any(self.normalize(w) in q for w in self.SEASON_WORDS)
        has_time = any(self.normalize(w) in q for w in self.TIME_WORDS)
        if has_season and (has_time or len(tokens) <= 5):
            return RouteResult(
                "current_season",
                self._canonical("current_season", language),
                1.0,
                "normalized_rule",
            )

        # Strong release/platform rules.
        release_words = ["نزل", "صدرت", "اصدار", "اطلاق", "release", "launch", "come out", "released"]
        if any(x in q for x in release_words):
            if any(x in q for x in ["موبايل", "android", "ios"]):
                return RouteResult("mobile_release", self._canonical("mobile_release", language), 1.0, "normalized_rule")
            if any(x in q for x in ["playstation", "ps5", "xbox", "console", "كونسل"]):
                return RouteResult("console_release", self._canonical("console_release", language), 1.0, "normalized_rule")
            if any(x in q for x in ["pc", "steam", "كمبيوتر", "حاسوب"]):
                return RouteResult("pc_release", self._canonical("pc_release", language), 1.0, "normalized_rule")

        # Exhaustive-list patterns.
        list_words = ["كل", "جميع", "قائمة", "اسماء", "عدد", "اريد", "list", "all", "every", "complete"]
        is_list = any(x in q for x in list_words)

        if is_list:
            if any(x in q for x in ["شخصيات", "شخصية", "operator", "operators", "character"]):
                return RouteResult("all_operators", self._canonical("all_operators", language), 0.99, "normalized_rule")
            if "operations" in q and any(x in q for x in ["خريطة", "خرائط", "map"]):
                return RouteResult("all_operations_maps", self._canonical("all_operations_maps", language), 0.99, "normalized_rule")
            if "warfare" in q and any(x in q for x in ["خريطة", "خرائط", "map"]):
                return RouteResult("all_warfare_maps", self._canonical("all_warfare_maps", language), 0.99, "normalized_rule")
            if any(x in q for x in ["طور", "اطوار", "mode", "modes"]):
                return RouteResult("all_modes", self._canonical("all_modes", language), 0.99, "normalized_rule")
            if any(x in q for x in ["مركبات", "مركبة", "vehicle", "vehicles", "دبابات", "طائرات"]):
                return RouteResult("all_vehicles", self._canonical("all_vehicles", language), 0.99, "normalized_rule")
            if any(x in q for x in ["boss", "bosses", "بوس", "بوسات", "زعماء", "warlord"]):
                return RouteResult("all_bosses", self._canonical("all_bosses", language), 0.99, "normalized_rule")
            if any(x in q for x in ["ذخيرة", "ذخائر", "عيارات", "ammo", "ammunition"]):
                return RouteResult("all_ammo", self._canonical("all_ammo", language), 0.99, "normalized_rule")
            if any(x in q for x in ["attachments", "attachment", "ملحقات", "اتاشمنت", "gunsmith"]):
                return RouteResult("all_attachments", self._canonical("all_attachments", language), 0.99, "normalized_rule")
            if any(x in q for x in ["انظمة", "نظام", "systems", "system"]):
                return RouteResult("all_systems", self._canonical("all_systems", language), 0.99, "normalized_rule")

            # Weapon category lists before generic weapons.
            if any(x in q for x in ["lmg", "رشاش خفيف", "رشاشات خفيفة"]):
                return RouteResult("all_lmg", self._canonical("all_lmg", language), 0.99, "normalized_rule")
            if any(x in q for x in ["shotgun", "شوزن", "بنادق صيد"]):
                return RouteResult("all_shotguns", self._canonical("all_shotguns", language), 0.99, "normalized_rule")
            if any(x in q for x in ["smg", "submachine", "رشاشات قصيرة"]):
                return RouteResult("all_smg", self._canonical("all_smg", language), 0.99, "normalized_rule")
            if any(x in q for x in ["sniper", "قناص", "قنص"]):
                return RouteResult("all_snipers", self._canonical("all_snipers", language), 0.99, "normalized_rule")
            if any(x in q for x in ["marksman", "dmr", "رامي مميز"]):
                return RouteResult("all_marksman", self._canonical("all_marksman", language), 0.99, "normalized_rule")
            if any(x in q for x in ["pistol", "مسدسات", "مسدس"]):
                return RouteResult("all_pistols", self._canonical("all_pistols", language), 0.99, "normalized_rule")
            if any(x in q for x in ["rifle", "بنادق", "بندقية"]):
                return RouteResult("all_rifles", self._canonical("all_rifles", language), 0.99, "normalized_rule")
            if any(x in q for x in ["سلاح", "اسلحة", "weapon", "weapons", "gun", "guns"]):
                return RouteResult("all_weapons", self._canonical("all_weapons", language), 0.99, "normalized_rule")

        # Versions / download / account.
        if any(x in q for x in ["garena", "global", "china", "نسخة", "نسخ"]):
            if any(x in q for x in ["فرق", "الفرق", "difference", "vs", "نسخ"]):
                return RouteResult("versions_overview", self._canonical("versions_overview", language), 0.96, "normalized_rule")
            if any(x in q for x in ["تحميل", "تنزيل", "اين", "download", "install"]):
                return RouteResult("download_overview", self._canonical("download_overview", language), 0.96, "normalized_rule")
            if any(x in q for x in ["حساب", "تقدم", "transfer", "account", "progress"]):
                return RouteResult("account_progression", self._canonical("account_progression", language), 0.96, "normalized_rule")

        return None

    def _ensure_vectors(self) -> None:
        if self._example_vectors is None:
            self._example_vectors = embed_texts(self._example_texts)

    def _semantic_route(self, question: str, language: str) -> RouteResult | None:
        self._ensure_vectors()
        qv = embed_query(question)

        # Embeddings are normalized by rag.embeddings.
        scores = self._example_vectors @ qv
        order = np.argsort(scores)[::-1]

        best_index = int(order[0])
        best_score = float(scores[best_index])
        best_intent = self._example_intents[best_index]
        best_example = self._example_texts[best_index]

        # Best score belonging to another intent, used as ambiguity margin.
        other_score = -1.0
        for idx in order[1:]:
            idx = int(idx)
            if self._example_intents[idx] != best_intent:
                other_score = float(scores[idx])
                break

        if (
            best_intent in self.DIRECT_INTENTS
            and best_score >= self.semantic_threshold
            and (other_score < 0 or best_score - other_score >= self.semantic_margin)
        ):
            return RouteResult(
                best_intent,
                self._canonical(best_intent, language),
                best_score,
                "semantic_embedding",
                best_example,
            )
        return None

    def _fuzzy_route(self, question: str, language: str) -> RouteResult | None:
        q = self.normalize(question)
        best = None

        for intent, cfg in self.intents.items():
            for example in cfg["examples"]:
                score = SequenceMatcher(None, q, self.normalize(example)).ratio()
                if best is None or score > best[0]:
                    best = (score, intent, example)

        if best and best[0] >= self.fuzzy_threshold and best[1] in self.DIRECT_INTENTS:
            return RouteResult(
                best[1],
                self._canonical(best[1], language),
                float(best[0]),
                "fuzzy_fallback",
                best[2],
            )
        return None

    def route(self, question: str) -> RouteResult | None:
        language = self.detect_language(question)

        # Fast, deterministic normalization rules first.
        direct = self._rule_route(question, language)
        if direct:
            return direct

        # Semantic matching handles paraphrases, dialects and word-order changes.
        try:
            semantic = self._semantic_route(question, language)
            if semantic:
                return semantic
        except Exception:
            # The application should still work if the embedding model is not
            # loaded yet or unavailable. Fuzzy matching is an offline fallback.
            pass

        return self._fuzzy_route(question, language)
