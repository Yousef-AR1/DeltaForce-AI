from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str | None = None) -> SentenceTransformer:
    return SentenceTransformer(model_name or settings.embedding_model)


def embed_texts(texts: Iterable[str], model_name: str | None = None) -> np.ndarray:
    values = list(texts)
    if not values:
        return np.empty((0, 0), dtype="float32")

    model = get_embedding_model(model_name)
    vectors = model.encode(
        values,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype="float32")


def embed_query(text: str, model_name: str | None = None) -> np.ndarray:
    return embed_texts([text], model_name=model_name)[0]
