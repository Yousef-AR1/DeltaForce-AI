from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from config import settings
from ingestion.chunker import chunk_text
from ingestion.loaders import discover_documents, load_file
from ingestion.metadata import infer_document_metadata
from rag.vector_store import FaissVectorStore


def load_curated_knowledge() -> list[dict]:
    return json.loads(settings.knowledge_path.read_text(encoding="utf-8"))


def load_document_chunks() -> list[dict]:
    output: list[dict] = []
    for path in discover_documents(settings.documents_dir):
        inferred = infer_document_metadata(path)
        for document in load_file(path):
            for i, chunk in enumerate(chunk_text(document["text"]), start=1):
                output.append(
                    {
                        "id": f"doc_{uuid4().hex[:12]}",
                        "title": f"{path.stem} - chunk {i}",
                        "content": chunk,
                        "category": "uploaded_document",
                        "knowledge_type": inferred["knowledge_type"],
                        "source_name": path.name,
                        "source_url": None,
                        "source_date": None,
                        "season": None,
                        "patch": None,
                        "language": "unknown",
                        "trust_level": inferred["trust_level"],
                        "is_current": inferred["knowledge_type"] != "historical",
                        "supersedes": None,
                        "tags": ["document", path.stem.lower()],
                        "source_file": document["source_file"],
                        "page": document["page"],
                    }
                )
    return output


def build_index() -> int:
    records = load_curated_knowledge() + load_document_chunks()
    store = FaissVectorStore()
    store.build(records)
    store.save()
    return len(records)


if __name__ == "__main__":
    count = build_index()
    print(f"Vector index built successfully with {count} records.")
