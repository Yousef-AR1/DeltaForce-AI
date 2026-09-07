from ingestion.chunker import chunk_text


def test_chunker_returns_overlapping_chunks():
    text = "A sentence. " * 300
    chunks = chunk_text(text, chunk_size=200, overlap=30)
    assert len(chunks) > 1
    assert all(chunks)
