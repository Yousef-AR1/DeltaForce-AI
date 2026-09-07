from __future__ import annotations

from pathlib import Path


def infer_document_metadata(path: Path) -> dict:
    parts = {p.lower() for p in path.parts}
    if "official" in parts:
        knowledge_type, trust = "official_fact", 1.0
    elif "historical" in parts:
        knowledge_type, trust = "historical", 0.95
    elif "esports" in parts:
        knowledge_type, trust = "official_fact", 0.95
    elif "community" in parts:
        knowledge_type, trust = "community", 0.55
    else:
        knowledge_type, trust = "community", 0.50
    return {"knowledge_type": knowledge_type, "trust_level": trust}
