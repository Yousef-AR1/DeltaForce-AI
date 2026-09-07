from __future__ import annotations

import json
import re
from pathlib import Path


class GameCatalogHit:
    def __init__(self, item: dict) -> None:
        self.item = item
        self.semantic_score = 1.0
        self.lexical_score = 1.0
        self.trust_weight = 1.0
        self.freshness_weight = 1.0
        self.type_weight = 1.0
        self.final_score = 1.0


class GameCatalogService:
    """Deterministic current-game catalog answers for exhaustive/list/freshness questions."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.snapshot = self._load("game_snapshot_2026-09-02.json")
        self.operators = self._load("operators_catalog.json")
        self.maps = self._load("maps_catalog.json")
        self.modes = self._load("modes_catalog.json")
        self.vehicles = self._load("vehicles_catalog.json")
        self.bosses = self._load("bosses_catalog.json")
        self.ammo = self._load("ammo_catalog.json")
        self.attachments = self._load("attachments_catalog_community.json")
        self.systems = self._load("systems_catalog.json")
        self.master = self._load("game_master_catalog.json")

    def _load(self, filename: str):
        return json.loads((self.data_dir / filename).read_text(encoding="utf-8"))

    @staticmethod
    def norm(text: str) -> str:
        text = text.lower().strip()
        text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _source(title: str, url: str, date: str = "2026-09-02",
                source_name: str = "Delta Force / Garena verified catalog",
                source_type: str = "official_fact") -> GameCatalogHit:
        return GameCatalogHit({
            "id": "v13_direct_game_catalog",
            "title": title,
            "content": "Structured current-game catalog used for exhaustive and freshness-aware answers.",
            "category": "game_master_catalog",
            "knowledge_type": source_type,
            "source_name": source_name,
            "source_url": url,
            "source_date": date,
            "language": "en",
            "trust_level": 1.0 if source_type == "official_fact" else 0.86,
            "is_current": True,
            "tags": ["v13", "master catalog", "current game data"],
        })

    def topic(self, question: str) -> str | None:
        q = self.norm(question)

        # Latest/current season must win over generic "mode/current".
        if any(x in q for x in [
            "اخر تحديث", "آخر تحديث", "التحديث الاخير", "التحديث الأخير",
            "الموسم الحالي", "السيزن الحالي", "شو الموسم", "شو السيزن",
            "latest update", "current season", "latest season", "what season",
            "reorientation", "rover", "الشخصية الجاية", "الشخصيه الجايه",
            "الاوبريتور الجاي", "الأوبريتور الجاي"
        ]):
            return "latest"

        if any(x in q for x in [
            "كلشي", "كل شي", "كل شيء", "كل معلومات اللعبة", "كل معلومات اللعبه",
            "شو عندك عن اللعبة", "شو عندك عن اللعبه", "everything", "master catalog",
            "all game content", "what do you know about the game"
        ]):
            return "master"

        if any(x in q for x in [
            "operator", "operators", "character", "characters",
            "شخصية", "شخصيات", "الشخصيات", "اوبريتور", "أوبريتور",
            "اوبريتورات", "العملاء", "عميل", "عملاء"
        ]):
            return "operators"

        if any(x in q for x in [
            "map", "maps", "خريطة", "خريطه", "خرائط", "الخرايط", "الخريطة", "الخريطه"
        ]):
            return "maps"

        if any(x in q for x in [
            "mode", "modes", "طور", "اطوار", "أطوار", "الاوضاع", "الأوضاع"
        ]):
            return "modes"

        if any(x in q for x in [
            "vehicle", "vehicles", "مركبة", "مركبه", "مركبات",
            "دبابة", "دبابه", "هليكوبتر", "طائرة", "طائره", "سيارة", "سياره"
        ]):
            return "vehicles"

        if any(x in q for x in [
            "boss", "bosses", "warlord", "بوس", "بوسات", "زعيم", "زعماء", "وورلورد"
        ]):
            return "bosses"

        if any(x in q for x in [
            "ammo", "ammunition", "ذخيرة", "ذخيره", "ذخائر", "رصاص", "عيارات", "عيار"
        ]):
            return "ammo"

        if any(x in q for x in [
            "attachment", "attachments", "اتاشمنت", "اتاشمنتات", "ملحق", "ملحقات",
            "تعديلات سلاح", "gunsmith parts"
        ]):
            return "attachments"

        if any(x in q for x in [
            "system", "systems", "نظام", "انظمة", "أنظمة", "black site", "السوق", "market",
            "auction", "safe box", "mandelbrick"
        ]):
            return "systems"

        return None

    def is_exhaustive_or_direct(self, question: str) -> bool:
        q = self.norm(question)
        topic = self.topic(question)
        if not topic:
            return False

        if topic in {"latest", "master"}:
            return True

        direct_words = [
            "جميع", "كل", "قائمة", "اسماء", "أسماء", "كم", "عدد", "اعطيني", "أعطيني",
            "شو هم", "شو هي", "ما هي", "ماهي", "مين هم", "مين الشخصيات",
            "all", "list", "how many", "names", "current", "latest"
        ]
        return any(self.norm(x) in q for x in direct_words)

    def can_handle(self, question: str) -> bool:
        return self.is_exhaustive_or_direct(question)

    def answer(self, question: str, language: str):
        topic = self.topic(question)
        if topic == "latest":
            return self.latest_answer(language)
        if topic == "master":
            return self.master_answer(language)
        if topic == "operators":
            return self.operators_answer(question, language)
        if topic == "maps":
            return self.maps_answer(question, language)
        if topic == "modes":
            return self.modes_answer(language)
        if topic == "vehicles":
            return self.vehicles_answer(language)
        if topic == "bosses":
            return self.bosses_answer(language)
        if topic == "ammo":
            return self.ammo_answer(language)
        if topic == "attachments":
            return self.attachments_answer(language)
        if topic == "systems":
            return self.systems_answer(language)
        return None

    def latest_answer(self, language: str):
        current = self.snapshot["current_season"]
        upcoming = self.snapshot["upcoming_season"]
        rover = self.snapshot["upcoming_operator"]
        if language == "ar":
            answer = (
                f"حتى **{self.snapshot['as_of']}**، الموسم الحالي هو **S{current['number']} - {current['name']}**. "
                f"آخر تحديث Live موثق في قاعدة المشروع هو **{self.snapshot['latest_live_update']['date']}**.\n\n"
                f"الموسم القادم **{upcoming['name']}** يبدأ رسميًا في **{upcoming['goes_live']}**، "
                f"ولذلك لا أعتبره Current قبل هذا التاريخ.\n\n"
                f"الشخصية القادمة: **{rover['codename']} ({rover['real_name']})** — فئة **{rover['class']}**، "
                f"ومعها **{rover['companion']}**. المعلومة المؤكدة حاليًا: Rover يعالج من بعيد وClover يتولى المطاردة.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                f"As of **{self.snapshot['as_of']}**, the current season is **S{current['number']} - {current['name']}**. "
                f"The latest live update tracked by this project is **{self.snapshot['latest_live_update']['date']}**.\n\n"
                f"**{upcoming['name']}** goes live on **{upcoming['goes_live']}**, so it is still upcoming. "
                f"Upcoming Support operator: **{rover['codename']} ({rover['real_name']})**, with **{rover['companion']}**.\n\n"
                "Sources: [S1] [S2]"
            )
        return answer, [
            self._source(
                "August 27 update / Reorientation preview",
                "https://deltaforce.garena.com/en/news/all/7K772J",
                "2026-08-26",
            ),
            self._source(
                "Rover coming to Reorientation",
                "https://steamcommunity.com/app/2507950/allnews/",
                "2026-08-24",
            ),
        ]

    def master_answer(self, language: str):
        c = self.master["coverage"]
        if language == "ar":
            answer = (
                f"قاعدة **DeltaForce AI V13** محدثة حتى **{self.master['as_of']}** وتغطي المحتوى الرئيسي للعبة:\n\n"
                f"- **الأسلحة:** {c['weapons_official_hq']} من كتالوج HQ الرسمي\n"
                f"- **الشخصيات الحالية:** {c['operators_current']} + شخصية قادمة واحدة (Rover)\n"
                f"- **خرائط Operations:** {c['operations_maps_official_hq']}\n"
                f"- **خرائط Warfare:** {c['warfare_maps_official_hq']} ظاهرة في HQ، و{c['warfare_maps_current_or_patch_referenced']} مع Monument المرجعية في الباتش\n"
                f"- **الأطوار الأساسية:** {c['core_modes']} + أطوار فرعية/متناوبة/تاريخية موثقة\n"
                f"- **المركبات الموثقة أو المرجعية:** {c['vehicles_verified_or_referenced']}\n"
                f"- **Bosses/Warlords:** {c['bosses_warlords_verified']}\n"
                f"- **عيارات Ammo المرجعية:** {c['ammo_caliber_reference']} + {c['meltdown_new_ammo_variants']} أنواع/Variants جديدة في Meltdown\n"
                f"- **Attachments:** مصدر المجتمع يسجل {c['community_attachment_reference_reported']} مدخلًا\n"
                f"- **Systems:** Black Site، Market، Auction House، Safe Box، Gear Tickets، Loot Ownership وغيرها.\n\n"
                f"الحالة الحالية: **{self.master['current_season']}**. القادم: **{self.master['upcoming']}**.\n\n"
                "القوائم الكاملة تُجاب من Structured Catalog بدل Top-K حتى لا يسقط منها أي اسم."
            )
        else:
            answer = (
                f"**DeltaForce AI V13** is current through **{self.master['as_of']}** and tracks the main game knowledge: "
                f"{c['weapons_official_hq']} official-HQ weapons, {c['operators_current']} current operators, maps, modes, "
                f"{c['vehicles_verified_or_referenced']} verified/referenced vehicles, bosses, ammo, systems and attachment references. "
                f"Current season: **{self.master['current_season']}**; upcoming: **{self.master['upcoming']}**. "
                "Exhaustive lists use structured catalogs rather than RAG Top-K."
            )
        return answer, [
            self._source("Delta Force Official HQ", "https://www.playdeltaforce.com/events/hq/"),
            self._source("Garena Delta Force latest update", "https://deltaforce.garena.com/en/news/all/7K772J", "2026-08-26"),
        ]

    def operators_answer(self, question: str, language: str):
        classes = self.operators["classes"]
        rover = self.operators["upcoming_operators"][0]
        if language == "ar":
            lines = [f"حتى **{self.operators['as_of']}** يوجد **{self.operators['current_count']} Operator حاليًا** موزعين على 4 فئات:"]
            arabic_class = {"Assault": "Assault", "Support": "Support", "Engineer": "Engineer", "Recon": "Recon"}
            for cls, names in classes.items():
                lines.append(f"\n### {arabic_class[cls]} — {len(names)}\n" + "، ".join(names))
            lines.append(
                f"\n### القادم\n**{rover['codename']} ({rover['real_name']})** — {rover['class']} — "
                f"يصل في **{rover['release_date']}** مع Reorientation، لذلك ليس ضمن الـ17 Current حتى الآن."
            )
            lines.append("\nالمصادر: [S1] [S2]")
        else:
            lines = [f"As of **{self.operators['as_of']}**, there are **{self.operators['current_count']} current operators** across four classes:"]
            for cls, names in classes.items():
                lines.append(f"\n### {cls} — {len(names)}\n" + ", ".join(names))
            lines.append(
                f"\n### Upcoming\n**{rover['codename']} ({rover['real_name']})** — {rover['class']} — "
                f"arrives **{rover['release_date']}** with Reorientation."
            )
            lines.append("\nSources: [S1] [S2]")
        return "\n".join(lines), [
            self._source(
                "S10 operator roster cross-check",
                "https://timesaver.gg/blog/delta-force-best-operators-tier-list",
                "2026-08-18",
                "Timesaver S10 roster cross-check",
                "community",
            ),
            self._source(
                "Rover official announcement",
                "https://steamcommunity.com/app/2507950/allnews/",
                "2026-08-24",
            ),
        ]

    def maps_answer(self, question: str, language: str):
        q = self.norm(question)
        wants_operations = "operations" in q or "عمليات" in q or "اوبريشن" in q
        wants_warfare = "warfare" in q or "وارفير" in q or "الحرب" in q

        op = [m["name"] for m in self.maps["operations"]["maps"]]
        wf = list(self.maps["warfare"]["official_hq_visible_maps"])
        extra = [m["name"] for m in self.maps["warfare"]["additional_current_patch_referenced_maps"]]

        if language == "ar":
            if wants_operations and not wants_warfare:
                answer = f"خرائط **Operations** الظاهرة حاليًا في HQ الرسمي عددها **{len(op)}**:\n\n" + "\n".join(f"- **{x}**" for x in op)
            elif wants_warfare and not wants_operations:
                answer = (
                    f"خرائط **Warfare** الظاهرة في HQ الرسمي عددها **{len(wf)}**:\n\n"
                    + "\n".join(f"- **{x}**" for x in wf)
                    + f"\n\nكما أن **{', '.join(extra)}** ما زالت مرجعية في Patch Meltdown الحالي، "
                    "لذلك أفصل بينها وبين قائمة HQ بدل حذفها أو اختراع حالة غير مؤكدة."
                )
            else:
                answer = (
                    f"### Operations — {len(op)}\n" + "، ".join(op) +
                    f"\n\n### Warfare — {len(wf)} ظاهرة في HQ\n" + "، ".join(wf) +
                    f"\n\n**Patch-referenced:** {', '.join(extra)}."
                )
            answer += "\n\nالمصادر: [S1] [S2]"
        else:
            answer = (
                f"Operations HQ maps ({len(op)}): {', '.join(op)}.\n\n"
                f"Warfare HQ-visible maps ({len(wf)}): {', '.join(wf)}.\n\n"
                f"Additional current-patch reference: {', '.join(extra)}.\n\nSources: [S1] [S2]"
            )
        return answer, [
            self._source("Official HQ map lists", "https://www.playdeltaforce.com/events/hq/"),
            self._source("Meltdown patch map references", "https://deltaforce.garena.com/en/news/all/2MX7J4", "2026-06-26"),
        ]

    def modes_answer(self, language: str):
        core = self.modes["core_modes"]
        wf = self.modes["warfare_submodes"]
        op = self.modes["operations_submodes"]
        if language == "ar":
            lines = ["الأطوار الأساسية الرسمية في Delta Force:"]
            for m in core:
                lines.append(f"- **{m['name']}** — {m['description']}")
            lines.append("\n### Warfare Submodes")
            for m in wf:
                lines.append(f"- **{m['name']}** — `{m['status']}`")
            lines.append("\n### Operations Submodes / Variants")
            for m in op:
                lines.append(f"- **{m['name']}** — `{m['status']}`")
            lines.append(
                "\n**مهم:** Limited/Rotating modes لا أصفها بأنها Live دائمًا؛ الحالة محفوظة حتى ما يخلط النظام بين الحالي والتاريخي."
            )
        else:
            lines = ["Official core modes:"]
            for m in core:
                lines.append(f"- **{m['name']}** — {m['description']}")
            lines.append("\n### Warfare submodes")
            for m in wf:
                lines.append(f"- **{m['name']}** — `{m['status']}`")
            lines.append("\n### Operations submodes / variants")
            for m in op:
                lines.append(f"- **{m['name']}** — `{m['status']}`")
        return "\n".join(lines), [
            self._source("Official core game modes", "https://deltaforce.garena.com/"),
            self._source("Official mode and balance updates", "https://deltaforce.garena.com/en/news/all/2MX7J4", "2026-06-26"),
        ]

    def vehicles_answer(self, language: str):
        entries = self.vehicles["verified_or_current_patch_referenced"]
        if language == "ar":
            lines = [f"عندي **{len(entries)} مركبة موثقة أو مذكورة في الباتشات الرسمية الحالية/الحديثة**:"]
            for v in entries:
                alias = f" ({v['alias']})" if v.get("alias") else ""
                lines.append(f"- **{v['name']}**{alias} — {v['type']} — `{v['status']}`")
            lines.append("\nالمصادر: Garena الرسمي + Patch Notes. [S1] [S2]")
        else:
            lines = [f"Verified or current-patch-referenced vehicles ({len(entries)}):"]
            for v in entries:
                alias = f" ({v['alias']})" if v.get("alias") else ""
                lines.append(f"- **{v['name']}**{alias} — {v['type']} — `{v['status']}`")
        return "\n".join(lines), [
            self._source("Garena vehicle showcase", "https://deltaforce.garena.com/"),
            self._source("Meltdown vehicle update", "https://deltaforce.garena.com/en/news/all/2MX7J4", "2026-06-26"),
        ]

    def bosses_answer(self, language: str):
        entries = self.bosses["verified_bosses_and_warlords"]
        if language == "ar":
            lines = [f"الـBosses / Warlords الموثقين في قاعدة V13 عددهم **{len(entries)}**:"]
            for b in entries:
                full = f" — {b['full_name']}" if b.get("full_name") else ""
                lines.append(f"- **{b['name']}**{full}: {b['context']}")
            lines.append("\nملاحظة: مواقع بعض الـBosses تتغير حسب Boss Rotation والأحداث.")
        else:
            lines = [f"Verified bosses / warlords tracked in V13 ({len(entries)}):"]
            for b in entries:
                lines.append(f"- **{b['name']}** — {b['context']}")
        return "\n".join(lines), [
            self._source("Official boss / warlord updates", "https://deltaforce.garena.com/en/news/all/2MX7J4", "2026-06-26"),
            self._source("Official boss rotation / older boss records", "https://deltaforce.garena.com/en/news/all/JQTVNF", "2026-07-30"),
        ]

    def ammo_answer(self, language: str):
        base = self.ammo["community_caliber_catalog"]
        new = self.ammo["meltdown_new_or_season_ammo_verified_official"]
        if language == "ar":
            answer = (
                f"### عيارات Ammo المرجعية — {len(base)}\n" + "، ".join(base) +
                f"\n\n### أنواع/Variants جديدة موثقة في Meltdown — {len(new)}\n" + "، ".join(new) +
                "\n\nالقائمة الأولى Community reference، أما إضافات Meltdown فموثقة من Patch Notes الرسمية."
            )
        else:
            answer = (
                f"### Reference ammo/calibers — {len(base)}\n" + ", ".join(base) +
                f"\n\n### Official Meltdown new/season variants — {len(new)}\n" + ", ".join(new)
            )
        return answer, [
            self._source(
                "Delta Force Database ammo reference",
                "https://deltaforcedb.com/wiki/ammo",
                "2026-08-01",
                "Delta Force Database",
                "community",
            ),
            self._source("Official Meltdown ammo update", "https://deltaforce.garena.com/en/news/all/2MX7J4", "2026-06-26"),
        ]

    def attachments_answer(self, language: str):
        names = self.attachments["names"]
        reported = self.attachments["source_count"]
        captured = self.attachments["captured_reference_names_count"]
        if language == "ar":
            answer = (
                f"مصدر **Delta Force Database** المجتمعي يسجل **{reported} Attachment**. "
                f"قاعدة V13 تحتوي أسماء مرجعية لـ **{captured}** منها:\n\n"
                + "\n".join(f"- {x}" for x in names)
                + "\n\nهذه Community Reference وليست بديلًا عن Patch Notes الرسمية عند سؤال Stats أو Availability."
            )
        else:
            answer = (
                f"Delta Force Database reports **{reported} attachment entries**. "
                f"V13 captured **{captured} reference names**:\n\n"
                + "\n".join(f"- {x}" for x in names)
                + "\n\nCommunity reference; official patch notes take precedence for live availability/stats."
            )
        return answer, [
            self._source(
                "Delta Force Database Attachments",
                "https://deltaforcedb.com/wiki/attachments",
                "2026-09-01",
                "Delta Force Database",
                "community",
            )
        ]

    def systems_answer(self, language: str):
        core = self.systems["core_reference_systems"]
        ops = self.systems["operations_systems_current_or_verified"]
        if language == "ar":
            answer = (
                "### الأنظمة المرجعية\n- " + "\n- ".join(core) +
                "\n\n### أنظمة Operations / Economy الموثقة\n- " + "\n- ".join(ops)
            )
        else:
            answer = (
                "### Reference systems\n- " + "\n- ".join(core) +
                "\n\n### Verified Operations / economy systems\n- " + "\n- ".join(ops)
            )
        return answer, [
            self._source("Delta Force HQ / systems", "https://www.playdeltaforce.com/events/hq/"),
            self._source("Official Operations system update", "https://deltaforce.garena.com/en/news/announcement/W9PGYU", "2025-09-01"),
        ]
