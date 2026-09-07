from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass
class QueryAnalysis:
    language: str
    intent: str
    freshness: str
    requested_year: int | None
    preferred_types: list[str]
    topic: str | None = None


def _detect_topic(q: str) -> str | None:
    topic_rules = [
        ("release_platform", [
            "release", "launch", "released", "mobile", "android", "ios", "console",
            "playstation", "xbox", "garena", "global", "china", "نسخة", "نسخه", "نسخ",
            "متى نزلت", "متى نزل", "متى صدرت", "تاريخ الاصدار", "تاريخ الإصدار",
            "موبايل", "اندرويد", "أندرويد", "ايفون", "آيفون", "كونسل", "بلايستيشن",
            "اكس بوكس", "إكس بوكس", "جارينا", "العالمية", "العالميه", "الصين",
            "تحميل", "تنزيل"
        ]),
        ("mena_esports", [
            "mena", "m.e.n.a", "middle east", "north africa", "emea",
            "turkey", "turkiye", "تركيا", "تركي", "مينا", "الشرق الأوسط",
            "الشرق الاوسط", "شمال افريقيا", "شمال أفريقيا", "العرب",
            "بطولات العرب", "بطولات مينا", "بطل مينا", "بطل العرب",
            "arab heroes", "أبطال العرب", "ابطال العرب",
            "ليلة الرعب", "night terror",
            "مقاتلي الصحراء", "desert fighters",
            "لعنة الفراعنة", "pharaoh",
            "بطولة العام الأول", "بطولة العام الاول", "first anniversary"
        ]),
        ("operations", ["operations", "operation mode", "طور العمليات", "طور operations", "عمليات"]),
        ("warfare", ["warfare", "طور الحرب", "طور warfare", "الحرب"]),
        ("black_hawk_down", ["black hawk down", "بلاك هوك داون"]),
        ("weapon", ["weapon", "weapons", "gun", "guns", "firearm", "rifle", "smg", "lmg", "sniper", "marksman", "pistol", "shotgun", "سلاح", "اسلحة", "اسلحه", "أسلحة", "رشاش", "رشاشات", "بندقية", "بنادق", "مسدس", "مسدسات", "قناص", "قنص", "شوزن"]),
        ("operator", ["operator", "operators", "character", "characters", "عميل", "عملاء", "شخصية", "شخصيات", "اوبريتور", "أوبريتور", "اوبريتورات"]),
        ("map", ["map", "maps", "خريطة", "خريطه", "خرائط", "خرايط", "ماب", "مابات"]),
        ("ammo", ["ammo", "ammunition", "ذخيرة"]),
        ("esports", ["esports", "tournament", "بطولة", "تنافسي"]),
    ]
    for topic, words in topic_rules:
        if any(w in q for w in words):
            return topic
    return None


def analyze_query(query: str) -> QueryAnalysis:
    q = query.strip().lower()
    language = "ar" if re.search(r"[\u0600-\u06FF]", query) else "en"

    # Small-talk / assistant identity queries are answered directly and do not need RAG.
    identity_phrases = [
        "who are you", "what are you", "what is your name", "your name",
        "tell me about yourself", "introduce yourself",
        "انت مين", "أنت مين", "مين انت", "مين أنت", "شو انت", "شو أنت",
        "ما انت", "ما أنت", "ما اسمك", "شو اسمك", "اسمك شو",
        "عرفني عنك", "عرّفني عنك", "عرفني عن حالك", "من انت", "من أنت",
    ]
    capability_phrases = [
        "what can you do", "how can you help", "what do you do",
        "what can i ask", "what can i ask you",
        "شو بتعمل", "شو بتقدر تعمل", "شو بتعرف تعمل", "بشو بتساعدني",
        "كيف بتساعدني", "شو بقدر اسألك", "شو بقدر أسألك", "شو اسألك",
        "ماذا تستطيع", "ماذا يمكنك", "شو اختصاصك", "ما تخصصك",
    ]
    greeting_phrases = [
        "hello", "hi", "hey", "مرحبا", "مرحباً", "هلا", "اهلا", "أهلا", "السلام عليكم"
    ]

    if any(p in q for p in identity_phrases):
        return QueryAnalysis(
            language=language,
            intent="identity",
            freshness="any",
            requested_year=None,
            preferred_types=[],
            topic="assistant_identity",
        )

    if any(p in q for p in capability_phrases):
        return QueryAnalysis(
            language=language,
            intent="capabilities",
            freshness="any",
            requested_year=None,
            preferred_types=[],
            topic="assistant_identity",
        )

    if q in greeting_phrases or any(q.startswith(p + " ") for p in greeting_phrases):
        return QueryAnalysis(
            language=language,
            intent="greeting",
            freshness="any",
            requested_year=None,
            preferred_types=[],
            topic="assistant_identity",
        )

    topic = _detect_topic(q)

    recommendation_words = [
        "best", "recommend", "strategy", "loadout", "composition", "tip",
        "افضل", "أفضل", "انصح", "نصيحة", "استراتيجية", "تشكيلة", "لوداوت",
    ]

    overview_phrases = [
        "what is", "what's", "explain", "overview", "tell me about",
        "how does the mode work", "mode about",
        "ما هو", "ماهو", "شو هو", "شو طور", "ما هو طور", "ماهو طور",
        "اشرح", "شرح", "شو فكرة", "ما فكرة", "فكرة الطور", "عرفني",
    ]

    historical_words = [
        "previous", "old", "before", "historical", "used to",
        "سابق", "قديم", "قبل", "تاريخ",
    ]
    current_words = [
        "current", "latest", "now", "today", "newest", "right now", "currently", " rn ",
        "حالي", "الحالي", "حاليا", "حالياً", "احدث", "أحدث", "الآن", "الان",
        "هسا", "هسه", "هلق", "هلأ", "الحين", "دحين", "دلوقتي", "دلوقت",
        "توا", "دابا", "دوك",
    ]

    if any(word in q for word in recommendation_words):
        intent = "recommendation"
        preferred_types = ["official_fact", "recommendation", "community"]
    elif any(phrase in q for phrase in overview_phrases) and topic in {
        "operations", "warfare", "black_hawk_down"
    }:
        intent = "overview"
        preferred_types = ["official_fact"]
    else:
        intent = "factual"
        preferred_types = ["official_fact", "historical"]

    if any(word in q for word in historical_words):
        freshness = "historical"
    elif any(word in q for word in current_words):
        freshness = "current"
    elif topic == "mena_esports":
        # Broad tournament-history questions should search completed and current records equally.
        freshness = "any"
    else:
        freshness = "current"

    years = re.findall(r"\b(20\d{2})\b", q)
    requested_year = int(years[0]) if years else None
    future_words = [
        "future", "will release", "will be", "coming in", "next season",
        "upcoming", "مستقبل", "سيصدر", "سينزل", "سيكون",
        "الموسم القادم", "القادم",
    ]
    if requested_year is not None and requested_year > date.today().year:
        freshness = "future_unknown"
    elif requested_year is not None and requested_year < date.today().year:
        freshness = "historical"
    elif any(word in q for word in future_words):
        freshness = "future_unknown"

    return QueryAnalysis(
        language=language,
        intent=intent,
        freshness=freshness,
        requested_year=requested_year,
        preferred_types=preferred_types,
        topic=topic,
    )
