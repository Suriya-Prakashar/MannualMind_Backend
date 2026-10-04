from app.services import ingestion_service


def test_ingest_pdf(monkeypatch):
    sample_pages = [
        {
            "page_number": 1,
            "text": (
                "Hydraulic filter maintenance "
                "procedure for the machine."
            ),
            "images": [],
        }
    ]

    sample_chunks = [
        {
            "chunk_id": "test_hash_page_1_chunk_1",
            "file_hash": "test_hash",
            "page_number": 1,
            "chunk_index": 1,
            "text": (
                "Hydraulic filter maintenance "
                "procedure for the machine."
            ),
            "images": [],
        }
    ]

    embedded_chunks = [
        {
            **sample_chunks[0],
            "embedding": [
                0.1,
                0.2,
                0.3,
            ],
        }
    ]

    stored_chunks = []

    monkeypatch.setattr(
        ingestion_service,
        "calculate_file_hash",
        lambda pdf_path: "test_hash",
    )

    monkeypatch.setattr(
        ingestion_service,
        "extract_text_and_images_from_pdf",
        lambda pdf_path, file_hash: sample_pages,
    )

    monkeypatch.setattr(
        ingestion_service,
        "create_page_chunks",
        lambda **kwargs: sample_chunks,
    )

    monkeypatch.setattr(
        ingestion_service,
        "find_chunk_by_id",
        lambda chunk_id: None,
    )

    monkeypatch.setattr(
        ingestion_service,
        "embed_chunks",
        lambda chunks: embedded_chunks,
    )

    def fake_create_chunk(chunk):
        stored_chunks.append(chunk)
        return "test_mongodb_id"

    monkeypatch.setattr(
        ingestion_service,
        "create_chunk",
        fake_create_chunk,
    )

    result = ingestion_service.ingest_pdf(
        "test.pdf"
    )

    assert result == {
        "file_hash": "test_hash",
        "total_pages": 1,
        "total_chunks": 1,
        "new_chunks": 1,
        "inserted_chunks": 1,
        "skipped_chunks": 0,
    }

    assert len(stored_chunks) == 1

    stored_chunk = stored_chunks[0]

    assert stored_chunk["chunk_id"] == (
        "test_hash_page_1_chunk_1"
    )

    assert stored_chunk["file_hash"] == "test_hash"
    assert stored_chunk["page_number"] == 1
    assert stored_chunk["chunk_index"] == 1

    assert stored_chunk["text"] == (
        "Hydraulic filter maintenance "
        "procedure for the machine."
    )

    assert stored_chunk["images"] == []

    assert stored_chunk["embedding"] == [
        0.1,
        0.2,
        0.3,
    ]


def test_ingest_pdf_skips_existing_chunk(
    monkeypatch,
):
    sample_pages = [
        {
            "page_number": 1,
            "text": "Existing hydraulic filter content.",
            "images": [],
        }
    ]

    sample_chunks = [
        {
            "chunk_id": "existing_hash_page_1_chunk_1",
            "file_hash": "existing_hash",
            "page_number": 1,
            "chunk_index": 1,
            "text": "Existing hydraulic filter content.",
            "images": [],
        }
    ]

    embedding_called = False

    def fake_embed_chunks(chunks):
        nonlocal embedding_called

        embedding_called = True

        return [
            {
                **chunks[0],
                "embedding": [
                    0.1,
                    0.2,
                    0.3,
                ],
            }
        ]

    monkeypatch.setattr(
        ingestion_service,
        "calculate_file_hash",
        lambda pdf_path: "existing_hash",
    )

    monkeypatch.setattr(
        ingestion_service,
        "extract_text_and_images_from_pdf",
        lambda pdf_path, file_hash: sample_pages,
    )

    monkeypatch.setattr(
        ingestion_service,
        "create_page_chunks",
        lambda **kwargs: sample_chunks,
    )

    monkeypatch.setattr(
        ingestion_service,
        "find_chunk_by_id",
        lambda chunk_id: {
            "chunk_id": chunk_id
        },
    )

    monkeypatch.setattr(
        ingestion_service,
        "embed_chunks",
        fake_embed_chunks,
    )

    result = ingestion_service.ingest_pdf(
        "test.pdf"
    )

    assert result == {
        "file_hash": "existing_hash",
        "total_pages": 1,
        "total_chunks": 1,
        "new_chunks": 0,
        "inserted_chunks": 0,
        "skipped_chunks": 1,
    }

    # Existing chunks must not trigger Gemini embedding.
    assert embedding_called is False

