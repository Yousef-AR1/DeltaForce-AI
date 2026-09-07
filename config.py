from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "DeltaForce AI")
    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    lmstudio_api_key: str = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
    model_name: str = "Qwen3-4B-Instruct-2507"
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    top_k_candidates: int = int(os.getenv("TOP_K_CANDIDATES", "24"))
    top_k_context: int = int(os.getenv("TOP_K_CONTEXT", "7"))
    min_retrieval_score: float = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.36"))
    max_context_chars: int = int(os.getenv("MAX_CONTEXT_CHARS", "14000"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.15"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "1200"))
    empty_response_retry_tokens: int = int(os.getenv("EMPTY_RESPONSE_RETRY_TOKENS", "1800"))
    retry_context_chars: int = int(os.getenv("RETRY_CONTEXT_CHARS", "6500"))
    lmstudio_request_timeout: float = float(os.getenv("LMSTUDIO_REQUEST_TIMEOUT", "120"))
    use_responses_fallback: bool = os.getenv("USE_RESPONSES_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}
    disable_qwen_thinking: bool = os.getenv("DISABLE_QWEN_THINKING", "true").strip().lower() in {"1", "true", "yes", "on"}
    lexical_bonus_weight: float = float(os.getenv("LEXICAL_BONUS_WEIGHT", "0.28"))

    knowledge_path: Path = BASE_DIR / "data" / "knowledge.json"
    sources_path: Path = BASE_DIR / "data" / "sources.json"
    patches_path: Path = BASE_DIR / "data" / "patches.json"
    documents_dir: Path = BASE_DIR / "data" / "documents"
    vector_index_path: Path = BASE_DIR / "vector_db" / "index.faiss"
    vector_metadata_path: Path = BASE_DIR / "vector_db" / "metadata.json"


settings = Settings()
