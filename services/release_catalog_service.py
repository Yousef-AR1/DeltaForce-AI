from __future__ import annotations

import json
import re
from pathlib import Path


class ReleaseCatalogHit:
    def __init__(self, item: dict) -> None:
        self.item = item
        self.semantic_score = 1.0
        self.lexical_score = 1.0
        self.trust_weight = 1.0
        self.freshness_weight = 1.0
        self.type_weight = 1.0
        self.final_score = 1.0


class ReleaseCatalogService:
    """Direct answers for release dates, platforms, editions, regions and download channels."""

    RELEASE_TERMS = [
        "release", "released", "launch", "launched", "release date",
        "متى نزلت", "متى نزل", "متى صدرت", "تاريخ الاصدار", "تاريخ الإصدار",
        "صدور اللعبة", "صدور اللعبه", "نزلت اللعبة", "نزلت اللعبه", "اطلاق", "إطلاق",
    ]
    MOBILE_TERMS = ["mobile", "android", "ios", "موبايل", "هاتف", "الهواتف", "اندرويد", "أندرويد", "ايفون", "آيفون"]
    PC_TERMS = ["pc", "computer", "steam", "epic", "كمبيوتر", "حاسوب", "الحاسب", "ستيم"]
    CONSOLE_TERMS = [
        "console", "ps5", "playstation", "xbox", "كونسل", "بلايستيشن", "بلاي ستيشن", "اكس بوكس", "إكس بوكس"
    ]
    VERSION_TERMS = [
        "version", "versions", "edition", "editions", "garena", "global", "china",
        "نسخة", "نسخه", "نسخ", "جارينا", "العالمية", "العالميه", "جلوبال", "الصينية", "الصينيه", "الصين"
    ]
    DOWNLOAD_TERMS = [
        "download", "where can i get", "where to get", "install",
        "وين انزل", "وين أنزل", "من وين انزل", "من وين أنزل", "وين احمل", "وين أحمل",
        "تحميل", "تنزيل", "متجر", "store"
    ]
    REGION_TERMS = [
        "country", "countries", "region", "regions", "available in", "supported in",
        "دولة", "دول", "بلد", "بلدان", "منطقة", "منطقه", "موجهة", "موجهه", "متاحة", "متاحه"
    ]
    ACCOUNT_TERMS = [
        "account", "accounts", "cross progression", "cross-progression", "transfer", "progress",
        "حساب", "حسابات", "تقدم", "نقل حساب", "نقل الحساب", "كروس بروجرشن", "مزامنة", "مزامنه"
    ]

    def __init__(self, path: Path) -> None:
        self.data = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def norm(text: str) -> str:
        text = text.lower().strip()
        text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
        return re.sub(r"\s+", " ", text)

    def _contains(self, question: str, terms: list[str]) -> bool:
        q = self.norm(question)
        return any(self.norm(t) in q for t in terms)

    def can_handle(self, question: str) -> bool:
        return any([
            self._contains(question, self.RELEASE_TERMS),
            self._contains(question, self.VERSION_TERMS),
            self._contains(question, self.DOWNLOAD_TERMS),
            self._contains(question, self.REGION_TERMS) and self._contains(question, self.VERSION_TERMS + self.DOWNLOAD_TERMS),
            self._contains(question, self.ACCOUNT_TERMS) and self._contains(question, self.VERSION_TERMS + ["steam", "mobile", "pc", "console"]),
        ])

    def _hit(self, title: str, url: str, source_name: str = "Official Delta Force / Garena source",
             date: str = "2026-09-02") -> ReleaseCatalogHit:
        return ReleaseCatalogHit({
            "id": "v14_release_catalog_direct",
            "title": title,
            "content": "Structured Delta Force release/version/platform catalog.",
            "category": "release_version_catalog",
            "knowledge_type": "official_fact",
            "source_name": source_name,
            "source_url": url,
            "source_date": date,
            "language": "en",
            "trust_level": 1.0,
            "is_current": True,
            "tags": ["release", "versions", "platforms", "garena", "global"],
        })

    def _detect_country(self, question: str) -> str | None:
        q = self.norm(question)
        aliases = self.data.get("country_aliases", {})
        for key, values in aliases.items():
            if any(self.norm(x) in q for x in values):
                return key
        return None

    def _is_ar(self, language: str) -> bool:
        return language == "ar"

    def answer(self, question: str, language: str):
        q = self.norm(question)

        # Exact platform release dates.
        if self._contains(question, self.MOBILE_TERMS) and self._contains(question, self.RELEASE_TERMS):
            return self.mobile_release(language)

        if self._contains(question, self.CONSOLE_TERMS) and self._contains(question, self.RELEASE_TERMS):
            return self.console_release(language)

        if self._contains(question, self.PC_TERMS) and self._contains(question, self.RELEASE_TERMS):
            return self.pc_release(language)

        # Country / region recommendation.
        country = self._detect_country(question)
        if country and (
            self._contains(question, self.DOWNLOAD_TERMS)
            or self._contains(question, self.VERSION_TERMS)
            or self._contains(question, self.REGION_TERMS)
        ):
            return self.country_version(country, language)

        # Download questions.
        if self._contains(question, self.DOWNLOAD_TERMS):
            if "garena" in q or "جارينا" in q:
                return self.garena_download(language)
            if "china" in q or "الصين" in q or "صيني" in q:
                return self.china_version(language)
            if self._contains(question, self.CONSOLE_TERMS):
                return self.console_release(language)
            return self.download_overview(language)

        # Account / progression / transfer questions.
        if self._contains(question, self.ACCOUNT_TERMS):
            return self.accounts_answer(language)

        # Version comparison / all editions.
        if self._contains(question, self.VERSION_TERMS):
            if "garena" in q or "جارينا" in q:
                return self.garena_version(language)
            if "china" in q or "الصين" in q or "صيني" in q:
                return self.china_version(language)
            return self.versions_overview(language)

        # Generic release/history.
        if self._contains(question, self.RELEASE_TERMS):
            return self.release_timeline(language)

        return None

    def mobile_release(self, language: str):
        if self._is_ar(language):
            answer = (
                "نسخة **Delta Force Mobile** العالمية صدرت رسميًا على **Android وiOS بتاريخ 21 أبريل 2025**.\n\n"
                "بالنسبة إلى **Garena MENA**، الإعلان العربي الرسمي أيضًا يحدد **21 أبريل 2025**. "
                "يوجد إعلان Garena إنجليزي إقليمي يذكر **22 أبريل 2025**، لذلك قاعدة المشروع تحفظ التاريخين "
                "ولا تخلط بينهما؛ عند السؤال عن MENA أستخدم تاريخ الإعلان العربي الرسمي: **21 أبريل**.\n\n"
                "للتنزيل: **Google Play** على Android و**Apple App Store** على iOS حسب النسخة والمنطقة.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                "**Delta Force Mobile** officially launched globally on **April 21, 2025** for Android and iOS. "
                "Garena's Arabic MENA announcement also uses April 21; a Garena English regional page lists April 22, "
                "so V14 preserves the regional date difference rather than overwriting it.\n\n"
                "Download through Google Play or the Apple App Store for the appropriate regional service.\n\n"
                "Sources: [S1] [S2]"
            )
        return answer, [
            self._hit(
                "Global mobile launch - April 21, 2025",
                "https://www.playdeltaforce.com/ar/detail/news-i-announced-the-global-launch-of-the-game-delta-force-on-mobile-devices-on-april-21-.html",
                "Delta Force official",
                "2025-04-19",
            ),
            self._hit(
                "Garena MENA mobile launch - April 21, 2025",
                "https://deltaforce.garena.com/ar/news/all/X9D53N",
                "Garena Delta Force MENA",
                "2025-03-13",
            ),
        ]

    def pc_release(self, language: str):
        if self._is_ar(language):
            answer = (
                "تاريخ PC له مرحلتان مهمتان:\n\n"
                "1. **5 ديسمبر 2024** — بدأت نسخة PC العالمية كـ **Global Open Beta بدون Reset للتقدم**، "
                "وكانت متاحة عبر **Official Launcher وSteam وEpic Games Store**.\n"
                "2. **21 أبريل 2025** — تم الإعلان عن **Global Official Launch** مع إطلاق الموبايل والموسم الجديد.\n\n"
                "أما **Garena PC** فبدأت رسميًا في **5 ديسمبر 2024** داخل مناطق Garena.\n\n"
                "إذا سألك أحد: «متى نزلت على PC؟» فالجواب المختصر هو **5 ديسمبر 2024**، "
                "ومع التوضيح أن Official Launch milestone اللاحق كان **21 أبريل 2025**.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                "PC has two important milestones:\n\n"
                "1. **December 5, 2024** — international PC Global Open Beta, no progression reset, "
                "via the official launcher, Steam and Epic Games Store.\n"
                "2. **April 21, 2025** — later Global Official Launch milestone alongside mobile.\n\n"
                "Garena PC also officially launched on **December 5, 2024** in Garena publishing regions.\n\n"
                "Sources: [S1] [S2]"
            )
        return answer, [
            self._hit(
                "PC Global Open Beta - December 5, 2024",
                "https://www.playdeltaforce.com/en/detail/news-announcement-pc-global-open-beta-on-dec-5.html",
                "Delta Force official",
                "2024-10-21",
            ),
            self._hit(
                "Garena PC launch - December 5, 2024",
                "https://deltaforce.garena.com/en/news/all/3UWGVS",
                "Garena Delta Force",
                "2024-12-03",
            ),
        ]

    def console_release(self, language: str):
        if self._is_ar(language):
            answer = (
                "صدرت **Delta Force على أجهزة الكونسول بتاريخ 19 أغسطس 2025** على:\n\n"
                "- **PlayStation 5 (PS5)**\n"
                "- **Xbox Series X|S**\n\n"
                "التنزيل من **PlayStation Store** أو **Microsoft/Xbox Store**، واللعبة Free-to-Play.\n\n"
                "لا توجد نسخة رسمية لـ **PS4 أو Xbox One** ضمن الإطلاق الحالي.\n"
                "نسخة الكونسول ليست Garena؛ Garena أعلنت نشرها للـPC والموبايل في مناطقها، بينما الكونسول عبر متاجر المنصات العالمية.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                "Delta Force launched on console on **August 19, 2025** for **PlayStation 5** and "
                "**Xbox Series X|S**. Download it from PlayStation Store or the Microsoft/Xbox Store. "
                "There is no current official PS4 or Xbox One release.\n\nSources: [S1] [S2]"
            )
        return answer, [
            self._hit(
                "PlayStation 5 release - August 19, 2025",
                "https://store.playstation.com/en-us/product/UP5104-PPSA28881_00-0555800169353087",
                "PlayStation Store",
                "2025-08-19",
            ),
            self._hit(
                "Xbox Series X|S release - August 19, 2025",
                "https://www.xbox.com/ar-ae/games/store/delta-force/9nrmzxgkp4nm",
                "Xbox Store",
                "2025-08-19",
            ),
        ]

    def release_timeline(self, language: str):
        if self._is_ar(language):
            answer = (
                "أهم تواريخ إصدار Delta Force الحديثة:\n\n"
                "- **20 أغسطس 2024:** تغيير الاسم من Delta Force: Hawk Ops إلى **Delta Force**.\n"
                "- **26 سبتمبر 2024:** إطلاق نسخة **الصين** على PC والموبايل.\n"
                "- **5 ديسمبر 2024:** إطلاق PC Global Open Beta + إطلاق Garena PC.\n"
                "- **21 أبريل 2025:** Global Official Launch + إطلاق الموبايل العالمي Android/iOS.\n"
                "- **21 أبريل 2025:** Garena MENA Mobile حسب الإعلان العربي الرسمي.\n"
                "- **19 أغسطس 2025:** إطلاق PS5 وXbox Series X|S.\n\n"
                "هذه التواريخ محفوظة كStructured Data حتى سؤال الإصدار لا يعتمد على تخمين الموديل."
            )
        else:
            answer = (
                "Key modern Delta Force release dates:\n"
                "- Aug 20, 2024: renamed from Delta Force: Hawk Ops to Delta Force.\n"
                "- Sep 26, 2024: Mainland China PC/mobile launch.\n"
                "- Dec 5, 2024: international PC Global Open Beta + Garena PC launch.\n"
                "- Apr 21, 2025: Global Official Launch + global Android/iOS mobile launch.\n"
                "- Aug 19, 2025: PS5 and Xbox Series X|S launch."
            )
        return answer, [
            self._hit("Delta Force release history", "https://steamcommunity.com/app/2507950/eventcomments/6015206955931891541/"),
            self._hit("Official global mobile launch", "https://www.playdeltaforce.com/ar/detail/news-i-announced-the-global-launch-of-the-game-delta-force-on-mobile-devices-on-april-21-.html", date="2025-04-19"),
        ]

    def versions_overview(self, language: str):
        if self._is_ar(language):
            answer = (
                "يوجد ثلاث بيئات نشر رئيسية لازم تفرق بينهم:\n\n"
                "### 1) Global / International\n"
                "- PC: Official Launcher + Steam + Epic Games Store\n"
                "- Mobile: Android + iOS\n"
                "- Console: PS5 + Xbox Series X|S\n"
                "- موجهة للخدمة الدولية، وتوفر المتجر قد يختلف حسب الدولة.\n\n"
                "### 2) Garena Delta Force\n"
                "- PC + Android + iOS\n"
                "- مناطق النشر الرسمية: **جنوب شرق آسيا، تايوان، أمريكا الوسطى والجنوبية، البرازيل، الشرق الأوسط وشمال أفريقيا**.\n"
                "- فيها فعاليات ومكافآت إقليمية وCross-progression بين Garena PC والموبايل.\n"
                "- ليست نسخة الكونسول.\n\n"
                "### 3) China / 三角洲行动\n"
                "- موجهة للصين القارية.\n"
                "- PC + Android + iOS.\n"
                "- أطلقت في **26 سبتمبر 2024**.\n"
                "- PC متوفر عبر WeGame، ولها نظام نشر وخوادم محلية منفصلة.\n\n"
                "**مهم:** لا أعتبر Global وGarena وChina نفس Account ecosystem. "
                "Garena كان لديها خدمة نقل Steam → Garena محدودة تاريخيًا بشروط وفترة، وهذا دليل أنها ليست مزامنة تلقائية دائمة.\n\n"
                "المصادر: [S1] [S2] [S3]"
            )
        else:
            answer = (
                "There are three main publishing/service ecosystems:\n\n"
                "1. **Global / International** — PC, Android, iOS, PS5, Xbox Series X|S.\n"
                "2. **Garena Delta Force** — PC + mobile in selected Garena regions: Southeast Asia, Taiwan, "
                "Central/South America, Brazil, Middle East and North Africa.\n"
                "3. **Mainland China / 三角洲行动** — domestic China PC/mobile service launched Sep 26, 2024.\n\n"
                "Do not assume accounts/progression are automatically interchangeable between these ecosystems.\n\n"
                "Sources: [S1] [S2] [S3]"
            )
        return answer, [
            self._hit(
                "Garena publishing regions",
                "https://deltaforce.garena.com/en/news/announcement/TZB3DE",
                "Garena Delta Force",
                "2024-11-05",
            ),
            self._hit(
                "Global PC launch platforms",
                "https://steamcommunity.com/app/2507950/discussions/0/4700161643034709416/",
                "Delta Force Steam community official moderator post",
                "2024-10-23",
            ),
            self._hit(
                "China domestic launch",
                "https://www.wegame.com.cn/act/release/df20240923/",
                "WeGame / Tencent",
                "2024-09-23",
            ),
        ]

    def garena_version(self, language: str):
        regions = "، ".join(self.data["services"]["garena"]["official_publishing_regions"])
        mena = "، ".join(self.data["services"]["garena"]["explicit_country_examples"]["mena_mobile_cbt_official_list"])
        if self._is_ar(language):
            answer = (
                "نسخة **Garena Delta Force** هي نسخة نشر إقليمية رسمية للـPC والموبايل.\n\n"
                f"مناطق Garena الرسمية: **{regions}**.\n\n"
                "في صفحة Garena MENA الرسمية الخاصة ببيتا الموبايل تم ذكر هذه البلدان بالاسم:\n"
                f"{mena}.\n\n"
                "هذا لا يعني أن القائمة السابقة هي قائمة الإطلاق الكاملة لكل مناطق Garena؛ "
                "هي قائمة دول مذكورة صراحة في اختبار MENA، بينما إعلان النشر الرسمي يحدد المناطق الأوسع.\n\n"
                "التنزيل: موقع Garena Delta Force الرسمي للـPC، وGoogle Play/App Store للموبايل.\n"
                "وتدعم Garena مزامنة التقدم بين Garena PC وGarena Mobile.\n\n"
                "المصادر: [S1] [S2] [S3]"
            )
        else:
            answer = (
                "Garena Delta Force is the official regional PC/mobile publishing service for "
                "Southeast Asia, Taiwan, Central/South America, Brazil, the Middle East and North Africa. "
                "PC downloads use the Garena Delta Force client/site; mobile uses regional Google Play/App Store listings. "
                "Garena supports PC/mobile cross-progression inside the Garena ecosystem.\n\nSources: [S1] [S2] [S3]"
            )
        return answer, [
            self._hit("Garena publishing regions", "https://deltaforce.garena.com/en/news/announcement/TZB3DE", "Garena Delta Force", "2024-11-05"),
            self._hit("Garena MENA explicit country list", "https://deltaforce.garena.com/ar/news/all/EWB7BJ", "Garena Delta Force MENA", "2025-02-07"),
            self._hit("Garena account / cross-progression FAQ", "https://deltaforce.garena.com/en/news/all/2PYFQX", "Garena Delta Force", "2025-04-02"),
        ]

    def garena_download(self, language: str):
        if self._is_ar(language):
            answer = (
                "لتنزيل **Garena Delta Force**:\n\n"
                "- **PC:** من موقع Garena Delta Force الرسمي وتشغيل Garena client الخاص باللعبة.\n"
                "- **Android:** Google Play من رابط/متجر Garena الإقليمي.\n"
                "- **iOS:** Apple App Store من رابط/متجر Garena الإقليمي.\n\n"
                "Garena مخصصة للنشر في جنوب شرق آسيا، تايوان، أمريكا الوسطى والجنوبية، البرازيل، MENA.\n"
                "إذا كنت في الأردن مثلًا، الأردن مذكورة رسميًا ضمن دول MENA في صفحة اختبار Garena Mobile.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                "Garena Delta Force downloads:\n"
                "- PC: Garena Delta Force official site/client.\n"
                "- Android: regional Garena Google Play listing.\n"
                "- iOS: regional Garena App Store listing.\n\nSources: [S1] [S2]"
            )
        return answer, [
            self._hit("Garena PC download / launch", "https://deltaforce.garena.com/en/news/all/3UWGVS", "Garena Delta Force", "2024-12-03"),
            self._hit("Garena Mobile store links / launch", "https://deltaforce.garena.com/ar/news/all/X9D53N", "Garena Delta Force MENA", "2025-03-13"),
        ]

    def china_version(self, language: str):
        if self._is_ar(language):
            answer = (
                "نسخة الصين اسمها **三角洲行动** وهي خدمة موجهة إلى **الصين القارية**.\n\n"
                "- الإطلاق الرسمي: **26 سبتمبر 2024**.\n"
                "- المنصات: **PC + Android + iOS**.\n"
                "- PC: يمكن تنزيلها عبر **WeGame**.\n"
                "- يوجد لها توزيع موبايل محلي، وTapTap يعرض Listing رسمي يدعم Android/iOS/PC.\n\n"
                "هذه نسخة Domestic منفصلة؛ قد تختلف مواعيد المواسم والمحتوى عن Global وGarena، "
                "ولا يجب افتراض مزامنة الحسابات بينها وبين النسخ الدولية.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                "The Mainland China domestic version is **三角洲行动**. It launched on **September 26, 2024** "
                "for PC, Android and iOS. PC distribution includes WeGame; Chinese mobile distribution uses local app channels. "
                "Treat it as a separate domestic service from Global/Garena.\n\nSources: [S1] [S2]"
            )
        return answer, [
            self._hit("China PC pre-download / launch", "https://www.wegame.com.cn/act/release/df20240923/", "WeGame / Tencent", "2024-09-23"),
            self._hit("China official app listing / launch date", "https://www.taptap.cn/app/330259", "TapTap official listing", "2024-09-26"),
        ]

    def download_overview(self, language: str):
        if self._is_ar(language):
            answer = (
                "أماكن تنزيل Delta Force تعتمد على النسخة والمنصة:\n\n"
                "### Global\n"
                "- PC: **Official Launcher / Steam / Epic Games Store**\n"
                "- Android: **Google Play**\n"
                "- iOS: **Apple App Store**\n"
                "- PS5: **PlayStation Store**\n"
                "- Xbox Series X|S: **Microsoft/Xbox Store**\n\n"
                "### Garena\n"
                "- PC: **Garena Delta Force official website/client**\n"
                "- Mobile: **Google Play / App Store** للمنطقة\n\n"
                "### China\n"
                "- PC: **WeGame**\n"
                "- Mobile: متاجر التطبيقات المحلية في الصين / Listings محلية مثل TapTap.\n\n"
                "إذا أعطيتني اسم بلدك أقدر أحدد لك النسخة الإقليمية الأنسب بناءً على البيانات الرسمية."
            )
        else:
            answer = (
                "Download channels depend on service and platform:\n"
                "- Global PC: official launcher / Steam / Epic Games Store\n"
                "- Global mobile: Google Play / Apple App Store\n"
                "- Console: PlayStation Store / Xbox Store\n"
                "- Garena PC: Garena Delta Force official client/site\n"
                "- Garena mobile: regional Google Play/App Store\n"
                "- China PC: WeGame; mobile uses Chinese local app distribution."
            )
        return answer, [
            self._hit("Global PC channels", "https://www.playdeltaforce.com/en/detail/news-announcement-pc-global-open-beta-on-dec-5.html"),
            self._hit("Garena PC channel", "https://deltaforce.garena.com/en/news/all/3UWGVS", "Garena Delta Force", "2024-12-03"),
        ]

    def accounts_answer(self, language: str):
        if self._is_ar(language):
            answer = (
                "بالنسبة للحسابات والتقدم:\n\n"
                "- **Garena PC ↔ Garena Mobile:** Cross-progression مدعوم داخل Garena.\n"
                "- **Global PC ↔ Mobile ↔ Console:** المصادر الرسمية للكونسول تصف Progression مشتركًا عبر المنصات عند ربط الحساب المناسب.\n"
                "- **Steam/Global ↔ Garena:** لا تعتبرهم مزامنة تلقائية. Garena شغلت خدمة نقل Steam → Garena تاريخية "
                "بشروط وفترة محددة (FAQ يذكر 4 أبريل إلى 30 يونيو 2025).\n"
                "- **China ↔ Global/Garena:** تعامل معها كخدمة منفصلة ولا تفترض نقل الحساب بدون إعلان رسمي.\n\n"
                "المصادر: [S1] [S2]"
            )
        else:
            answer = (
                "Account/progression summary:\n"
                "- Garena PC ↔ Garena Mobile: cross-progression supported inside Garena.\n"
                "- Global PC ↔ Mobile ↔ Console: shared progression is supported with the appropriate linked global account.\n"
                "- Global/Steam ↔ Garena: do not assume automatic sync; Garena ran a historical limited transfer program.\n"
                "- China: treat as a separate domestic ecosystem unless an official migration is announced.\n\nSources: [S1] [S2]"
            )
        return answer, [
            self._hit("Garena account FAQ", "https://deltaforce.garena.com/en/news/all/2PYFQX", "Garena Delta Force", "2025-04-02"),
            self._hit("Global multi-platform progression", "https://news.xbox.com/en-us/2025/07/16/the-delta-force-technical-test-is-live-today-for-xbox-insiders/", "Xbox Wire / Delta Force", "2025-07-16"),
        ]

    def country_version(self, country: str, language: str):
        garena = self.data["services"]["garena"]["explicit_country_examples"]
        garena_countries = set()
        for group in ["mena_mobile_cbt_official_list", "sea_official_test_list", "latam_mobile_cbt_examples"]:
            garena_countries.update(self.norm(x) for x in garena[group])

        aliases = self.data["country_aliases"].get(country, [])
        display = aliases[0] if aliases else country
        is_china = country == "china"

        # Check if canonical English country name is in explicit lists.
        canonical_map = {
            "jordan": "Jordan", "saudi_arabia": "Saudi Arabia", "uae": "United Arab Emirates",
            "egypt": "Egypt", "iraq": "Iraq", "kuwait": "Kuwait", "qatar": "Qatar",
            "bahrain": "Bahrain", "oman": "Oman", "lebanon": "Lebanon", "morocco": "Morocco",
            "algeria": "Algeria", "tunisia": "Tunisia", "libya": "Libya", "turkey": "Turkey",
            "indonesia": "Indonesia", "thailand": "Thailand", "vietnam": "Vietnam",
            "singapore": "Singapore", "malaysia": "Malaysia", "philippines": "Philippines",
            "taiwan": "Taiwan", "brazil": "Brazil", "mexico": "Mexico", "colombia": "Colombia",
            "china": "Mainland China",
        }
        name = canonical_map.get(country, display)
        explicit_garena = self.norm(name) in garena_countries or country == "taiwan"

        if is_china:
            return self.china_version(language)

        if self._is_ar(language):
            if explicit_garena:
                answer = (
                    f"بالنسبة إلى **{name}**: هي ضمن منطقة نشر Garena أو مذكورة صراحة في صفحات Garena الإقليمية/الاختبارية. "
                    "إذا هدفك اللعب على الخدمة الإقليمية وفعاليات Garena، استخدم **Garena Delta Force** للـPC أو الموبايل.\n\n"
                    "أما Global فقد يعتمد توفرها على المتجر والدولة، لذلك لا أقول إنها ممنوعة أو متاحة في كل الحالات بدون فحص Store الحالي. "
                    "الأهم: لا تخلط حساب Garena مع Global كأنهما نفس Ecosystem.\n\n"
                    "المصدر: [S1]"
                )
            else:
                answer = (
                    f"بالنسبة إلى **{name}**، لا أملك قائمة رسمية كاملة تثبت أنها دولة Garena بالاسم من المصادر الحالية. "
                    "إعلان Garena يحدد مناطق واسعة فقط. استخدم Store/الموقع الرسمي المتاح في بلدك، "
                    "ولا أخمن نسخة إقليمية بدون مصدر."
                )
        else:
            if explicit_garena:
                answer = (
                    f"**{name}** is inside a Garena publishing region or is explicitly named in a Garena regional/test page. "
                    "Use Garena Delta Force if you want the Garena regional ecosystem/events. Global storefront availability can still vary; "
                    "do not treat Garena and Global accounts as the same ecosystem.\n\nSource: [S1]"
                )
            else:
                answer = (
                    f"I do not have an official exhaustive country-by-country mapping for **{name}**. "
                    "Garena publishes broader regional coverage, while Global storefront availability varies by store/country."
                )
        return answer, [
            self._hit("Garena publishing regions", "https://deltaforce.garena.com/en/news/announcement/TZB3DE", "Garena Delta Force", "2024-11-05")
        ]
