from __future__ import annotations

import html
import json
import re
import random

from markdown_it import MarkdownIt
import streamlit as st

from config import settings
from ingestion.indexer import build_index
from llm.lmstudio import EmptyModelResponseError, LMStudioClient
from rag.query_analyzer import analyze_query
from services.chat_service import ChatService


AR_QUICK_QUESTION_POOL = [
    "متى نزلت Delta Force على الموبايل؟",
    "متى نزلت اللعبة على PS5 وXbox؟",
    "شو الفرق بين نسخة Garena والنسخة العالمية؟",
    "أنا بالأردن، أي نسخة Delta Force أنزل؟",
    "اعطيني جميع الشخصيات الحالية",
    "اعطيني جميع أسلحة فئة الرشاش الخفيف",
    "اعطيني جميع خرائط Operations الحالية",
    "شو آخر تحديث والموسم الحالي؟",
    "من بطل Arab Heroes 2026؟",
    "من بطل بطولة MENA x TURKEY 2026؟",
    "ما هو طور Operations؟",
    "اعطيني كل أطوار اللعبة",
    "اعطيني جميع المركبات",
    "شو النسخ الموجودة من Delta Force ووين أنزل كل نسخة؟",
    "هل حساب Garena نفس حساب Steam أو Global؟",
    "متى نزلت نسخة الصين من Delta Force؟",
    "انت مين وشو بتقدر تعمل؟",
    "شو جميع أسلحة الشوزن؟",
]

EN_QUICK_QUESTION_POOL = [
    "When did Delta Force Mobile officially launch?",
    "When did Delta Force launch on PS5 and Xbox Series X|S?",
    "What is the difference between Garena and Global Delta Force?",
    "Where can I download each Delta Force version?",
    "List all current Delta Force operators.",
    "List every LMG in Delta Force.",
    "List all current Operations maps.",
    "What is the current season and latest update?",
    "Who won Arab Heroes 2026?",
    "Who won MENA x TURKEY 2026?",
    "What is Operations mode?",
    "List the tracked Delta Force game modes.",
    "List the verified vehicles in Delta Force.",
    "What are the Global, Garena, and China versions?",
    "Does progression transfer between Garena and Global?",
    "When did the Mainland China version launch?",
    "Who are you and what can you do?",
    "List every shotgun in Delta Force.",
]


def generate_demo_questions() -> dict[str, list[str]]:
    return {
        "ar": random.sample(AR_QUICK_QUESTION_POOL, 3),
        "en": random.sample(EN_QUICK_QUESTION_POOL, 3),
    }


# =============================================================================
# Page configuration
# =============================================================================
st.set_page_config(
    page_title="DeltaForce AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": True})


def contains_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def render_chat_text(text: str) -> None:
    if not contains_arabic(text):
        st.markdown(text)
        return

    rendered_html = _MARKDOWN.render(text)
    st.markdown(
        f'<div class="df-arabic-message" dir="rtl">{rendered_html}</div>',
        unsafe_allow_html=True,
    )


def safe_text(value: object, fallback: str = "N/A") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def render_status_badge(label: str, ok: bool) -> str:
    cls = "df-status-ok" if ok else "df-status-off"
    icon = "●" if ok else "○"
    return f'<span class="df-status {cls}">{icon}&nbsp; {html.escape(label)}</span>'


def render_source_card(index: int, hit) -> None:
    item = hit.item
    title = html.escape(safe_text(item.get("title"), "Evidence"))
    source_name = html.escape(safe_text(item.get("source_name"), "Knowledge Base"))
    source_date = html.escape(safe_text(item.get("source_date")))
    source_type = html.escape(safe_text(item.get("knowledge_type")).replace("_", " ").title())
    patch = html.escape(safe_text(item.get("patch") or item.get("season")))
    score = f"{hit.final_score:.3f}"

    url = safe_text(item.get("source_url"), "")
    if url.startswith(("http://", "https://")):
        source_link = f'<a href="{html.escape(url)}" target="_blank">Open source ↗</a>'
    elif url:
        source_link = '<span class="df-local-source">Verified local archive</span>'
    else:
        source_link = ""

    st.markdown(
        f"""
        <div class="df-source-card">
            <div class="df-source-head">
                <strong>[S{index}] {title}</strong>
                <span class="df-score">Score {score}</span>
            </div>
            <div class="df-source-meta">
                <span>{source_type}</span>
                <span>{source_name}</span>
                <span>{source_date}</span>
                <span>{patch}</span>
                {source_link}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Interface styles
# =============================================================================
st.markdown(
    """
    <style>
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 5rem;
    }

    [data-testid="stSidebar"] {
        min-width: 300px;
    }

    .df-brand {
        display: flex;
        align-items: center;
        gap: 0.9rem;
        margin-bottom: 0.25rem;
    }

    .df-brand-icon {
        font-size: 2.2rem;
    }

    .df-brand-title {
        font-size: 2rem;
        line-height: 1;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    .df-subtitle {
        opacity: 0.72;
        margin-top: 0.55rem;
        margin-bottom: 0.9rem;
        font-size: 0.98rem;
    }

    .df-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin: 0.75rem 0 1.3rem 0;
    }

    .df-chip {
        display: inline-flex;
        align-items: center;
        border: 1px solid rgba(128,128,128,0.28);
        border-radius: 999px;
        padding: 0.32rem 0.68rem;
        font-size: 0.82rem;
        opacity: 0.88;
        background: rgba(128,128,128,0.06);
    }

    .df-status-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }

    .df-status {
        display: inline-flex;
        align-items: center;
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-size: 0.78rem;
        background: rgba(128,128,128,0.05);
    }

    .df-status-ok {
        color: #52c781;
    }

    .df-status-off {
        color: #db7c7c;
    }

    .df-hero {
        border: 1px solid rgba(128,128,128,0.22);
        border-radius: 18px;
        padding: 1.35rem 1.5rem;
        margin: 0.9rem 0 1.2rem 0;
        background: rgba(128,128,128,0.045);
    }

    .df-hero h3 {
        margin: 0 0 0.35rem 0;
        font-size: 1.18rem;
    }

    .df-hero p {
        margin: 0;
        opacity: 0.74;
        line-height: 1.7;
    }

    [data-testid="stChatMessage"] {
        border: 1px solid rgba(128,128,128,0.13);
        border-radius: 16px;
        padding: 0.35rem 0.4rem;
        margin-bottom: 0.7rem;
        font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    }

    .df-arabic-message {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
        font-family: Tahoma, "Segoe UI", Arial, sans-serif;
        font-size: 1.04rem;
        line-height: 2;
        width: 100%;
    }

    .df-arabic-message p,
    .df-arabic-message li,
    .df-arabic-message h1,
    .df-arabic-message h2,
    .df-arabic-message h3,
    .df-arabic-message h4,
    .df-arabic-message blockquote {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
    }

    .df-arabic-message ul,
    .df-arabic-message ol {
        direction: rtl;
        text-align: right;
        padding-right: 1.6rem;
        padding-left: 0;
    }

    .df-arabic-message code,
    .df-arabic-message pre {
        direction: ltr;
        text-align: left;
        unicode-bidi: isolate;
        font-family: Consolas, "Courier New", monospace;
    }

    [data-testid="stChatInput"] textarea {
        unicode-bidi: plaintext;
        font-family: Tahoma, "Segoe UI", Arial, sans-serif;
    }

    .df-source-card {
        border: 1px solid rgba(128,128,128,0.20);
        border-radius: 12px;
        padding: 0.72rem 0.82rem;
        margin-bottom: 0.55rem;
        background: rgba(128,128,128,0.035);
    }

    .df-source-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
        margin-bottom: 0.35rem;
    }

    .df-score {
        white-space: nowrap;
        font-size: 0.76rem;
        opacity: 0.65;
    }

    .df-source-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.3rem 0.8rem;
        font-size: 0.78rem;
        opacity: 0.70;
    }

    .df-source-meta a {
        text-decoration: none;
    }

    .df-local-source {
        font-weight: 600;
    }

    .df-answer-meta {
        margin-top: 0.35rem;
        font-size: 0.78rem;
        opacity: 0.62;
    }

    .df-demo-label {
        font-size: 0.82rem;
        opacity: 0.65;
        margin-bottom: 0.35rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 14px;
        padding: 0.7rem 0.9rem;
        background: rgba(128,128,128,0.035);
    }

    @media (max-width: 700px) {
        .df-brand-title {
            font-size: 1.65rem;
        }

        .block-container {
            padding-top: 1.25rem;
        }

        .df-source-head {
            display: block;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# State
# =============================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_service" not in st.session_state:
    st.session_state.chat_service = ChatService()
if "quick_question" not in st.session_state:
    st.session_state.quick_question = None
if "demo_questions" not in st.session_state:
    st.session_state.demo_questions = generate_demo_questions()

lm = LMStudioClient()

try:
    lm_ok, lm_status = lm.ping()
except Exception as exc:
    lm_ok, lm_status = False, str(exc)

try:
    curated = json.loads(settings.knowledge_path.read_text(encoding="utf-8"))
    knowledge_count = len(curated)
except Exception:
    knowledge_count = 0

index_ready = settings.vector_index_path.exists() and settings.vector_metadata_path.exists()

try:
    indexed_metadata = (
        json.loads(settings.vector_metadata_path.read_text(encoding="utf-8"))
        if settings.vector_metadata_path.exists()
        else []
    )
    indexed_count = len(indexed_metadata)
except Exception:
    indexed_count = 0


# =============================================================================
# Sidebar
# =============================================================================
with st.sidebar:
    st.markdown("## 🎯 DeltaForce AI")
    st.caption("Local, source-grounded assistant")

    st.markdown("### AI Model")
    st.caption("`Qwen3-4B-Instruct-2507`")

    st.markdown("### System status")
    st.markdown(
        '<div class="df-status-row">'
        + render_status_badge("LM Studio", lm_ok)
        + render_status_badge("Knowledge Index", index_ready)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    presentation_mode = st.toggle(
        "Technical Details",
        value=False,
    )

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.quick_question = None
        st.session_state.demo_questions = generate_demo_questions()
        st.rerun()

    with st.expander("About this assistant"):
        st.markdown(
            """
            **DeltaForce AI** specializes in:
            - Game modes and mechanics
            - Weapons, ammo and operators
            - Operations and Warfare
            - Esports and tournament rules
            - Garena Delta Force MENA tournament history
            - Release dates, platforms and regional versions
            - Arabic and English questions
            """
        )

    with st.expander("🛠️ System controls", expanded=False):
        if st.button("Test AI model", use_container_width=True):
            with st.spinner("Testing model generation..."):
                model_ok, model_status = lm.quick_test()
            st.success(model_status) if model_ok else st.error(model_status)

        st.write("Knowledge records:", knowledge_count)
        st.write("Indexed chunks:", indexed_count)
        st.write("Vector index:", "Ready" if index_ready else "Not built")

        if st.button("Build / Rebuild FAISS index", use_container_width=True):
            with st.spinner("Building semantic vector index..."):
                count = build_index()
            st.success(f"Indexed {count} records/chunks.")
            st.rerun()

        if not lm_ok:
            st.warning("LM Studio is not reachable.")
            if presentation_mode:
                st.caption(lm_status)


# =============================================================================
# Header
# =============================================================================
st.markdown(
    """
    <div class="df-brand">
        <div class="df-brand-icon">🎯</div>
        <div class="df-brand-title">DeltaForce AI</div>
    </div>
    <div class="df-subtitle">
        Your specialized AI assistant for Delta Force — releases, versions, platforms, weapons, operators, maps, modes and MENA Esports.
    </div>
    <div class="df-badges">
        <span class="df-chip">🔎 Grounded RAG</span>
        <span class="df-chip">🧠 Local LLM</span>
        <span class="df-chip">🌐 Arabic + English + Dialects</span>
        <span class="df-chip">📅 Releases & Versions</span>
        <span class="df-chip">🗂️ Latest Game Catalog</span>
        <span class="df-chip">🏆 Garena MENA Archive</span>
        <span class="df-chip">📚 Source-aware answers</span>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Knowledge Base", f"{knowledge_count:,}", help="Curated game and esports knowledge records")
with col2:
    st.metric("Vector Search", "Ready" if index_ready else "Setup needed", help="FAISS semantic retrieval")
with col3:
    st.metric("Local AI", "Connected" if lm_ok else "Offline", help="LM Studio local inference status")


# =============================================================================
# Welcome / demo shortcuts
# =============================================================================
if not st.session_state.messages:
    st.markdown(
        """
        <div class="df-hero">
            <h3>Ask naturally. DeltaForce AI retrieves the evidence first.</h3>
            <p>
                Ask naturally in Arabic dialects or English about the game, weapons, Operations, Warfare,
                operators, release dates, Global/Garena/China versions, tournament rules, or Garena MENA esports history.
                Answers are grounded in the project knowledge base whenever reliable evidence is available.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="df-demo-label">Quick questions for the live demo — 3 Arabic + 3 English</div>', unsafe_allow_html=True)

    demo = st.session_state.demo_questions

    st.markdown("**العربية**")
    ar_cols = st.columns(3)
    for i, question_text in enumerate(demo["ar"]):
        with ar_cols[i]:
            if st.button(
                f"🇯🇴 {question_text}",
                key=f"demo_ar_{i}",
                use_container_width=True,
            ):
                st.session_state.quick_question = question_text

    st.markdown("**English**")
    en_cols = st.columns(3)
    for i, question_text in enumerate(demo["en"]):
        with en_cols[i]:
            if st.button(
                f"🌐 {question_text}",
                key=f"demo_en_{i}",
                use_container_width=True,
            ):
                st.session_state.quick_question = question_text

    if st.button("🔄 Change demo questions", use_container_width=True):
        st.session_state.demo_questions = generate_demo_questions()
        st.rerun()


# =============================================================================
# Existing conversation
# =============================================================================
for message in st.session_state.messages:
    avatar = "🎮" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        render_chat_text(message["content"])

        sources = message.get("sources", [])
        if sources:
            st.markdown(
                f'<div class="df-answer-meta">Grounded with {len(sources)} retrieved source(s)</div>',
                unsafe_allow_html=True,
            )
            with st.expander(f"📚 Sources used ({len(sources)})"):
                for i, hit in enumerate(sources, start=1):
                    render_source_card(i, hit)


# =============================================================================
# New question
# =============================================================================
typed_question = st.chat_input("Ask about Delta Force / اسأل عن Delta Force")
question = st.session_state.quick_question or typed_question

if question:
    st.session_state.quick_question = None

    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user", avatar="🎮"):
        render_chat_text(question)

    preview = analyze_query(question)
    direct_query = st.session_state.chat_service.is_direct_query(question)

    with st.chat_message("assistant", avatar="🤖"):
        answer = ""
        hits = []
        result = None

        if direct_query:
            result = st.session_state.chat_service.ask(question)
            answer = result.answer
            render_chat_text(answer)

        elif not index_ready:
            answer = (
                "قاعدة البحث الدلالي غير جاهزة بعد. يرجى بناء الـVector Index من إعدادات النظام."
                if contains_arabic(question)
                else "The semantic search index is not ready yet. Build the Vector Index from system settings."
            )
            st.warning(answer)

        elif not lm_ok:
            answer = (
                "الموديل Qwen3-4B-Instruct-2507 غير محمّل في LM Studio."
                if contains_arabic(question)
                else "Qwen3-4B-Instruct-2507 is not loaded in LM Studio."
            )
            st.warning(answer)

        else:
            try:
                with st.spinner("Searching trusted knowledge and preparing the answer..."):
                    result = st.session_state.chat_service.ask(question)

                answer = result.answer
                hits = result.hits
                render_chat_text(answer)

                if result.generation_mode == "safe_abstention":
                    st.info(
                        "No sufficiently reliable evidence was found, so the assistant avoided guessing."
                    )
                elif result.generation_mode == "evidence_fallback" and presentation_mode:
                    st.info(
                        "LM Studio returned no final text, so trusted retrieved evidence was used."
                    )

                if hits:
                    st.markdown(
                        f'<div class="df-answer-meta">Grounded with {len(hits)} retrieved source(s)</div>',
                        unsafe_allow_html=True,
                    )
                    with st.expander(f"📚 Sources used ({len(hits)})"):
                        for i, hit in enumerate(hits, start=1):
                            render_source_card(i, hit)

                if presentation_mode:
                    with st.expander("Technical details", expanded=False):
                        st.markdown(
                            f"""
                            **Pipeline:** Query Analysis → Embedding → FAISS Retrieval → Re-ranking → Context Validation → Local LLM  
                            **Intent:** `{result.analysis.intent}`  
                            **Topic:** `{getattr(result.analysis, "topic", None) or "N/A"}`  
                            **Freshness:** `{result.analysis.freshness}`  
                            **Grounded:** `{result.grounded}`  
                            **Generation mode:** `{result.generation_mode}`  
                            **Retrieved evidence:** `{len(result.hits)}`  
                            **Semantic/Dialect route:** `{getattr(st.session_state.chat_service.last_route, "intent", None) or "No direct semantic route"}`  
                            **Route method:** `{getattr(st.session_state.chat_service.last_route, "method", None) or "N/A"}`  
                            **Route confidence:** `{getattr(st.session_state.chat_service.last_route, "confidence", 0.0):.3f}`  
                            **Validation:** {result.reason}
                            """
                        )

            except EmptyModelResponseError as exc:
                answer = (
                    "تعذر إنشاء الإجابة من Qwen3-4B-Instruct-2507. تأكد أن الموديل محمّل في LM Studio."
                    if contains_arabic(question)
                    else "Qwen3-4B-Instruct-2507 could not generate a final answer. Make sure it is loaded in LM Studio."
                )
                st.error(answer)
                if presentation_mode:
                    st.caption(str(exc))

            except Exception as exc:
                answer = (
                    "حدث خطأ أثناء معالجة السؤال. جرّب مرة أخرى."
                    if contains_arabic(question)
                    else "An error occurred while processing the question. Try again."
                )
                st.error(answer)
                if presentation_mode:
                    st.exception(exc)

    stored_sources = hits if result is not None else []
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": stored_sources,
        }
    )
