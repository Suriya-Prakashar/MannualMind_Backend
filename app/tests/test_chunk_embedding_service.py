from app.services import chunk_embedding_service


def test_embed_chunks(monkeypatch):

    def fake_generate_embedding(text: str):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(
        chunk_embedding_service,
        "generate_embedding",
        fake_generate_embedding,
    )

    chunks = [
        {
            "chunk_id": "test_page_1_chunk_1",
            "file_hash": "test_hash",
            "page_number": 1,
            "chunk_index": 1,
            "text": "Hydraulic filter maintenance",
            "images": [],
        },
        {
            "chunk_id": "test_page_1_chunk_2",
            "file_hash": "test_hash",
            "page_number": 1,
            "chunk_index": 2,
            "text": "",
            "images": [],
        },
    ]

    embedded_chunks = (
        chunk_embedding_service.embed_chunks(chunks)
    )

    assert len(embedded_chunks) == 1

    result = embedded_chunks[0]

    assert result["chunk_id"] == "test_page_1_chunk_1"
    assert result["file_hash"] == "test_hash"
    assert result["page_number"] == 1
    assert result["chunk_index"] == 1
    assert result["text"] == "Hydraulic filter maintenance"
    assert result["images"] == []
    assert result["embedding"] == [0.1, 0.2, 0.3]