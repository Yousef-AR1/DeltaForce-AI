from __future__ import annotations

from config import BASE_DIR
from rag.rag_engine import DeltaForceRAG, RagResponse
from rag.query_analyzer import analyze_query
from services.weapon_catalog_service import WeaponCatalogService
from services.game_catalog_service import GameCatalogService
from services.release_catalog_service import ReleaseCatalogService
from services.semantic_intent_router import SemanticIntentRouter


class ChatService:
    def __init__(self) -> None:
        self.rag = DeltaForceRAG()
        self.weapon_catalog = WeaponCatalogService(BASE_DIR / "data" / "weapons_catalog.json")
        self.game_catalog = GameCatalogService(BASE_DIR / "data")
        self.release_catalog = ReleaseCatalogService(BASE_DIR / "data" / "release_versions_catalog.json")
        self.intent_router = SemanticIntentRouter(BASE_DIR / "data" / "intent_router_examples.json")
        self.last_weapon_category: str | None = None
        self.last_route = None

    def _route_question(self, question: str):
        route = self.intent_router.route(question)
        self.last_route = route
        return route

    def is_direct_query(self, question: str) -> bool:
        analysis = analyze_query(question)
        if analysis.intent in {"identity", "capabilities", "greeting"}:
            return True

        route = self._route_question(question)
        routed_question = route.canonical_query if route else question

        return (
            route is not None
            or self.release_catalog.can_handle(routed_question)
            or self.game_catalog.can_handle(routed_question)
            or self.weapon_catalog.is_list_question(routed_question)
            or self.weapon_catalog.is_followup(routed_question)
            or self.weapon_catalog.asks_category(routed_question)
        )

    def ask(self, question: str) -> RagResponse:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")
        analysis = analyze_query(question)
        language = analysis.language

        route = self._route_question(question)
        routed_question = route.canonical_query if route else question

        if route and route.intent == "identity":
            return self.rag.ask(routed_question)
        if route and route.intent == "capabilities":
            return self.rag.ask(routed_question)

        if self.release_catalog.can_handle(routed_question):
            direct = self.release_catalog.answer(routed_question, language)
            if direct:
                answer, hits = direct
                return RagResponse(
                    answer, True,
                    ("Structured V14 release/version catalog direct answer; fixed platform facts bypassed RAG Top-K." + (f" IntentRouter={route.intent}/{route.method}/{route.confidence:.3f}" if route else "")),
                    analysis, hits, "release_catalog_direct"
                )

        if self.game_catalog.can_handle(routed_question):
            direct = self.game_catalog.answer(routed_question, language)
            if direct:
                answer, hits = direct
                return RagResponse(
                    answer, True,
                    ("Structured game catalog direct answer; exhaustive list/freshness query bypassed RAG Top-K." + (f" IntentRouter={route.intent}/{route.method}/{route.confidence:.3f}" if route else "")),
                    analysis, hits, "game_catalog_direct"
                )

        if self.weapon_catalog.is_followup(routed_question) and self.last_weapon_category:
            answer, hits = self.weapon_catalog.category_answer(
                self.last_weapon_category, language, followup=True
            )
            return RagResponse(
                answer, True,
                "Contextual weapon follow-up resolved from the complete official structured catalog.",
                analysis, hits, "weapon_catalog_direct"
            )

        category = self.weapon_catalog.detect_category(routed_question)

        if self.weapon_catalog.is_list_question(routed_question) and category:
            self.last_weapon_category = category
            answer, hits = self.weapon_catalog.category_answer(category, language)
            return RagResponse(
                answer, True,
                ("Complete category returned directly from the official structured catalog; RAG Top-K bypassed." + (f" IntentRouter={route.intent}/{route.method}/{route.confidence:.3f}" if route else "")),
                analysis, hits, "weapon_catalog_direct"
            )

        if self.weapon_catalog.is_list_question(routed_question) and category is None:
            self.last_weapon_category = None
            answer, hits = self.weapon_catalog.all_answer(language)
            return RagResponse(
                answer, True,
                ("Complete weapon catalog returned directly from the official structured catalog." + (f" IntentRouter={route.intent}/{route.method}/{route.confidence:.3f}" if route else "")),
                analysis, hits, "weapon_catalog_direct"
            )

        if self.weapon_catalog.asks_category(routed_question):
            result = self.weapon_catalog.category_of_weapon_answer(routed_question, language)
            if result:
                answer, hits = result
                return RagResponse(
                    answer, True,
                    "Weapon category returned directly from the official structured catalog.",
                    analysis, hits, "weapon_catalog_direct"
                )

        if category:
            self.last_weapon_category = category

        return self.rag.ask(question)
