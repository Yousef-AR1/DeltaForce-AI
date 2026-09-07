from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

from config import settings

REQUIRED = {
    "id", "title", "content", "category", "knowledge_type", "source_name",
    "source_date", "trust_level", "is_current", "tags"
}
ALLOWED_TYPES = {"official_fact", "historical", "recommendation", "community", "system_policy"}


def validate() -> None:
    data = json.loads(settings.knowledge_path.read_text(encoding="utf-8"))
    ids = [x.get("id") for x in data]
    duplicates = [k for k, v in Counter(ids).items() if v > 1]
    errors = []
    if duplicates:
        errors.append(f"Duplicate IDs: {duplicates}")

    for i, item in enumerate(data):
        missing = REQUIRED - item.keys()
        if missing:
            errors.append(f"Record {i} ({item.get('id')}): missing {sorted(missing)}")
        if item.get("knowledge_type") not in ALLOWED_TYPES:
            errors.append(f"Record {item.get('id')}: invalid knowledge_type")
        trust = item.get("trust_level")
        if not isinstance(trust, (int, float)) or not 0 <= trust <= 1:
            errors.append(f"Record {item.get('id')}: trust_level must be 0..1")
        raw_date = item.get("source_date")
        if raw_date:
            try:
                datetime.strptime(raw_date, "%Y-%m-%d")
            except ValueError:
                errors.append(f"Record {item.get('id')}: invalid source_date {raw_date}")
        if item.get("knowledge_type") == "official_fact" and item.get("trust_level", 0) >= 0.9 and not item.get("source_url"):
            errors.append(f"Record {item.get('id')}: trusted official fact has no source_url")

    if errors:
        print("Knowledge validation FAILED")
        for error in errors:
            print("-", error)
        raise SystemExit(1)

    print(f"Knowledge validation passed: {len(data)} records")


if __name__ == "__main__":
    validate()
