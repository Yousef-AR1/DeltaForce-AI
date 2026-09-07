from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from config import settings
from rag.embeddings import embed_query, embed_texts


@dataclass
class SearchHit:
    item: dict[str, Any]
    semantic_score: float


class FaissVectorStore:
    def __init__(self) -> None:
        self.index: faiss.Index | None = None
        self.metadata: list[dict[str, Any]] = []

    @property
    def ready(self) -> bool:
        return self.index is not None and bool(self.metadata)

    def build(self, records: list[dict[str, Any]]) -> None:
        if not records:
            raise ValueError("Cannot build a vector store with no records.")

        texts = [self._embedding_text(record) for record in records]
        vectors = embed_texts(texts)
        if vectors.ndim != 2 or vectors.shape[0] != len(records):
            raise RuntimeError("Embedding output shape does not match input records.")

        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        self.metadata = records

    def save(
        self,
        index_path: Path = settings.vector_index_path,
        metadata_path: Path = settings.vector_metadata_path,
    ) -> None:
        if not self.ready:
            raise RuntimeError("Vector store is not built.")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(index_path))
        metadata_path.write_text(
            json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load(
        self,
        index_path: Path = settings.vector_index_path,
        metadata_path: Path = settings.vector_metadata_path,
    ) -> None:
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError("Vector index is missing. Run: python -m ingestion.indexer")
        self.index = faiss.read_index(str(index_path))
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if self.index.ntotal != len(self.metadata):
            raise RuntimeError("FAISS index and metadata are out of sync.")

    def search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        if not self.ready:
            self.load()
        assert self.index is not None

        q = embed_query(query).reshape(1, -1).astype("float32")
        count = min(top_k, len(self.metadata))
        scores, indices = self.index.search(q, count)
        hits: list[SearchHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            hits.append(SearchHit(item=self.metadata[int(idx)], semantic_score=float(score)))
        return hits

    @staticmethod
    def _embedding_text(record: dict[str, Any]) -> str:
        tags = " ".join(record.get("tags", []))
        return (
            f"{record.get('title', '')}\n"
            f"Category: {record.get('category', '')}\n"
            f"Type: {record.get('knowledge_type', '')}\n"
            f"Tags: {tags}\n"
            f"{record.get('content', '')}"
        )
