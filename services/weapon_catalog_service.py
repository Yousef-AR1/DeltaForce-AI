from __future__ import annotations

import json
import re
from pathlib import Path


class CatalogHit:
    def __init__(self, item: dict) -> None:
        self.item = item
        self.semantic_score = 1.0
        self.lexical_score = 1.0
        self.trust_weight = 1.0
        self.freshness_weight = 1.0
        self.type_weight = 1.0
        self.final_score = 1.0


class WeaponCatalogService:
    """Complete official weapon lists that do not get truncated by RAG Top-K."""

    CATEGORY_ALIASES = {
        "lmg": [
            "lmg", "light machine gun", "general machine gun",
            "رشاش خفيف", "رشاشات خفيفة", "الرشاش الخفيف", "الرشاشات الخفيفة",
            "رشاش عام", "رشاشات عامة"
        ],
        "smg": [
            "smg", "submachine gun", "submachine",
            "رشاش قصير", "رشاشات قصيرة", "الرشاشات القصيرة", "رشاش صغير"
        ],
        "sniper": [
            "sniper rifle", "sniper", "بنادق القنص", "بندقية قنص", "قناص", "قنص"
        ],
        "marksman": [
            "marksman rifle", "marksman", "dmr",
            "رامي مميز", "الرامي المميز", "بندقية رامي", "ماركسمان"
        ],
        "shotgun": [
            "shotgun", "shotguns", "شوزن", "شوتجن",
            "بندقية صيد", "بنادق الصيد", "بنادق صيد"
        ],
        "pistol": [
            "pistol", "pistols", "handgun", "مسدس", "مسدسات", "المسدسات"
        ],
        "special": [
            "special weapon", "special weapons", "سلاح خاص", "أسلحة خاصة", "اسلحة خاصة"
        ],
        "rifle": [
            "assault rifle", "battle rifle", "rifle", "rifles",
            "بندقية هجومية", "بنادق هجومية", "البنادق الهجومية",
            "بندقية قتالية", "بنادق قتالية", "فئة البنادق", "بنادق"
        ],
    }

    LIST_WORDS = [
        "all", "list", "names", "every", "complete", "how many",
        "جميع", "كل", "قائمة", "اسماء", "أسماء", "كم عدد",
        "اعطيني", "أعطيني", "هات", "شو الاسلحة", "شو الأسلحة",
        "ما هي الاسلحة", "ما هي الأسلحة", "ماهي الاسلحة", "ماهي الأسلحة",
    ]

    FOLLOWUPS = [
        "في اسلحة اخرى", "في أسلحة أخرى", "في اسلحه اخرى",
        "في اسلحة ثانية", "في أسلحة ثانية", "غيرهم", "غيرها",
        "في غيرهم", "في كمان", "other weapons", "any others",
        "anything else", "more weapons", "are there more",
    ]

    CATEGORY_QUESTIONS = [
        "what type", "what category", "which category",
        "شو نوع", "ما نوع", "شو فئة", "ما فئة", "اي فئة", "أي فئة", "تصنيف"
    ]

    def __init__(self, path: Path) -> None:
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.categories = {c["id"]: c for c in self.data["categories"]}

    @staticmethod
    def norm(text: str) -> str:
        text = text.lower().strip()
        text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
        return re.sub(r"\s+", " ", text)

    def detect_category(self, question: str) -> str | None:
        q = self.norm(question)
        for cid in ["lmg", "smg", "sniper", "marksman", "shotgun", "pistol", "special", "rifle"]:
            for alias in sorted(self.CATEGORY_ALIASES[cid], key=len, reverse=True):
                if self.norm(alias) in q:
                    return cid
        return None

    def is_followup(self, question: str) -> bool:
        q = self.norm(question)
        return any(self.norm(x) in q for x in self.FOLLOWUPS)

    def is_list_question(self, question: str) -> bool:
        q = self.norm(question)
        has_list = any(self.norm(x) in q for x in self.LIST_WORDS)
        has_weapon = any(x in q for x in [
            "weapon", "weapons", "gun", "guns", "firearm",
            "سلاح", "اسلحة", "اسلحه", "الاسلحة", "الاسلحه"
        ])
        return has_list and (has_weapon or self.detect_category(question) is not None)

    def asks_category(self, question: str) -> bool:
        q = self.norm(question)
        return any(self.norm(x) in q for x in self.CATEGORY_QUESTIONS)

    def find_weapon(self, question: str):
        q = self.norm(question)
        candidates = []
        for cat in self.data["categories"]:
            for w in cat["weapons"]:
                candidates.append((w["name"], w, cat))
        for name, w, cat in sorted(candidates, key=lambda x: len(x[0]), reverse=True):
            n = self.norm(name)
            if re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", q):
                return w, cat
        return None

    def _source_hit(self, title: str) -> CatalogHit:
        return CatalogHit({
            "id": "v12_official_weapon_catalog",
            "title": title,
            "content": "Complete current firearm catalog from Delta Force Official HQ Tool Station.",
            "category": "weapon_catalog",
            "knowledge_type": "official_fact",
            "source_name": self.data["source_name"],
            "source_url": self.data["source_url"],
            "source_date": self.data["verified_at"],
            "language": "en",
            "trust_level": 1.0,
            "is_current": True,
            "tags": ["official", "weapon catalog", "complete list"],
        })

    def category_answer(self, cid: str, language: str, followup: bool = False):
        cat = self.categories[cid]
        names = [w["name"] for w in cat["weapons"]]

        if language == "ar":
            intro = (
                f"لا، حسب **القائمة الرسمية الحالية** هذه هي جميع أسلحة فئة "
                f"**{cat['name_ar']}**، وعددها **{len(names)}**:"
                if followup else
                f"حسب **Delta Force Official HQ**، فئة **{cat['name_ar']}** "
                f"تحتوي حاليًا على **{len(names)}** أسلحة:"
            )
            body = "\n".join(f"- **{n}**" for n in names)
            note = ""
            if cid == "lmg":
                note = (
                    "\n\n**ملاحظة:** فئة LMG الرسمية تجمع Light Machine Gun وGeneral Machine Gun، "
                    "لذلك القائمة الكاملة هي **M249، PKM، M250، QJB201**."
                )
            answer = f"{intro}\n\n{body}{note}\n\nالمصدر: **Delta Force Official HQ Tool Station** [S1]"
        else:
            intro = (
                f"No. This is the complete current official **{cat['name_en']}** list (**{len(names)}** total):"
                if followup else
                f"The current official **{cat['name_en']}** category contains **{len(names)}** weapons:"
            )
            body = "\n".join(f"- **{n}**" for n in names)
            answer = f"{intro}\n\n{body}\n\nSource: **Delta Force Official HQ Tool Station** [S1]"

        return answer, [self._source_hit(f"Complete official weapon list — {cat['name_en']}")]

    def all_answer(self, language: str):
        total = self.data["total_weapons"]
        lines = []
        if language == "ar":
            lines.append(f"حسب **Delta Force Official HQ**، القائمة الحالية تحتوي على **{total} سلاحًا** ضمن 8 فئات:")
            for cat in self.data["categories"]:
                names = "، ".join(w["name"] for w in cat["weapons"])
                lines.append(f"\n### {cat['name_ar']} — {len(cat['weapons'])}\n{names}")
            lines.append("\nالمصدر: **Delta Force Official HQ Tool Station** [S1]")
        else:
            lines.append(f"The current **Delta Force Official HQ** catalog contains **{total} weapons** across 8 categories:")
            for cat in self.data["categories"]:
                names = ", ".join(w["name"] for w in cat["weapons"])
                lines.append(f"\n### {cat['name_en']} — {len(cat['weapons'])}\n{names}")
            lines.append("\nSource: **Delta Force Official HQ Tool Station** [S1]")
        return "\n".join(lines), [self._source_hit("Complete official Delta Force firearm catalog")]

    def category_of_weapon_answer(self, question: str, language: str):
        found = self.find_weapon(question)
        if not found:
            return None
        weapon, cat = found
        if language == "ar":
            answer = (
                f"سلاح **{weapon['name']}** موجود في القائمة الرسمية الحالية، وتصنيفه ضمن "
                f"**{cat['name_ar']}**.\n\nالمصدر: **Delta Force Official HQ Tool Station** [S1]"
            )
        else:
            answer = (
                f"**{weapon['name']}** is present in the current official catalog under "
                f"**{cat['name_en']}**.\n\nSource: **Delta Force Official HQ Tool Station** [S1]"
            )
        return answer, [self._source_hit(f"{weapon['name']} — official weapon category")]
