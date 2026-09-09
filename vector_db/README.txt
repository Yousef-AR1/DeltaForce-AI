This folder is intentionally shipped without a prebuilt FAISS binary because the index depends on the embedding model installed on the target machine.
Build it locally with:

    python -m ingestion.indexer

The command creates index.faiss and metadata.json from data/knowledge.json plus supported documents.
