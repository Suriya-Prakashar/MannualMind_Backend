"""
Test Suite: Document Ingestion, PDF Processing, Chunking & Persistence
Consolidates and validates:
- SHA-256 file hashing
- PyMuPDF text & diagram extraction
- Chunk generation & metadata preservation
- Duplicate chunk prevention & repository operations
- Database connection lifecycle
- End-to-end ingestion pipeline (skipping duplicates & zero-waste embeddings)
"""
import uuid
from unittest.mock import MagicMock, patch
import pymupdf
import pytest
from pymongo.errors import DuplicateKeyError

from app.database import mongodb
from app.services.core import ingestion_service
from app.services.core.chunk_service import create_page_chunks
from app.services.core.pdf_service import extract_text_and_images_from_pdf
from app.services.repositories.chunk_repository import (
    create_chunk,
    create_chunks,
    find_chunk_by_id,
)
from app.services.utils.file_hash import calculate_file_hash


# ---------------------------------------------------------------------------
# 1. File Hashing
# ---------------------------------------------------------------------------
def test_calculate_file_hash(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("ManualMind test content", encoding="utf-8")
    file_hash = calculate_file_hash(str(test_file))
    assert isinstance(file_hash, str)
    assert len(file_hash) == 64


# ---------------------------------------------------------------------------
# 2. PDF Extraction (Text & Images)
# ---------------------------------------------------------------------------
def test_extract_text_and_images_from_pdf(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    image_path = tmp_path / "test_image.png"

    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 1)
    pixmap.save(str(image_path))

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        pymupdf.Point(50, 50),
        "ManualMind PDF test page",
    )
    page.insert_image(
        pymupdf.Rect(100, 100, 200, 200),
        filename=str(image_path),
    )
    document.save(str(pdf_path))
    document.close()

    file_hash = "test_pdf_hash"
    pages = extract_text_and_images_from_pdf(
        str(pdf_path),
        file_hash,
    )

    assert len(pages) == 1
    page_data = pages[0]
    assert page_data["page_number"] == 1
    assert "ManualMind PDF test page" in page_data["text"]
    assert len(page_data["images"]) == 1
    image_data = page_data["images"][0]
    assert image_data["image_id"] == "page_1_image_1"
    assert image_data["filename"] == "page_1_image_1.png"
    assert image_data["path"]


# ---------------------------------------------------------------------------
# 3. Chunking Service
# ---------------------------------------------------------------------------
def test_create_page_chunks():
    sample_text = (
        "The hydraulic filter is located on the left side of the hydraulic assembly.\n"
        "Before removing the filter, switch off the machine and release hydraulic pressure.\n"
        "Remove the filter housing carefully and inspect the filter element."
    )
    file_hash = "abc123testhash"
    page_number = 12
    images = [{"image_id": "page_12_image_1", "filename": "filter.png"}]

    chunks = create_page_chunks(
        text=sample_text,
        file_hash=file_hash,
        page_number=page_number,
        images=images,
        chunk_size=100,
        chunk_overlap=25,
    )

    assert len(chunks) > 0
    for index, chunk in enumerate(chunks, start=1):
        assert chunk["chunk_id"] == f"{file_hash}_page_{page_number}_chunk_{index}"
        assert chunk["file_hash"] == file_hash
        assert chunk["page_number"] == page_number
        assert chunk["chunk_index"] == index
        assert chunk["text"]
        assert chunk["images"] == images


# ---------------------------------------------------------------------------
# 4. Database Lifecycle & Repository CRUD
# ---------------------------------------------------------------------------
def test_mongodb_connection_lifecycle():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_db.name = "manualmind"
    mock_collection = MagicMock()
    mock_collection.name = "documents"
    mock_chunks = MagicMock()
    mock_chunks.name = "chunks"

    def get_collection(name):
        return mock_chunks if name == "chunks" else mock_collection

    mock_db.__getitem__.side_effect = get_collection
    mock_client.__getitem__.return_value = mock_db

    with patch("app.database.MongoClient", return_value=mock_client):
        mongodb.connect()
        assert mongodb.database is not None
        assert mongodb.collection is not None
        assert mongodb.chunks_collection is not None
        mock_client.admin.command.assert_called_once_with("ping")
        mongodb.close()
        assert mongodb.client is None


def test_chunk_repository_crud():
    mongodb.connect()
    chunk_id = f"test_chunk_{uuid.uuid4().hex}"
    chunk = {
        "chunk_id": chunk_id,
        "file_hash": "test_file_hash",
        "page_number": 1,
        "chunk_index": 1,
        "text": "Hydraulic filter maintenance",
        "images": [],
        "embedding": [0.1, 0.2, 0.3],
    }

    try:
        inserted_id = create_chunk(chunk)
        assert inserted_id is not None

        stored_chunk = find_chunk_by_id(chunk_id)
        assert stored_chunk is not None
        assert stored_chunk["chunk_id"] == chunk_id
        assert stored_chunk["text"] == "Hydraulic filter maintenance"
        assert stored_chunk["embedding"] == [0.1, 0.2, 0.3]
    finally:
        mongodb.chunks_collection.delete_one({"chunk_id": chunk_id})
        mongodb.close()


def test_duplicate_chunk_is_rejected():
    mongodb.connect()
    chunk = {
        "chunk_id": "duplicate_test_chunk",
        "file_hash": "duplicate_test_file",
        "page_number": 1,
        "chunk_index": 1,
        "text": "Duplicate chunk test",
        "images": [],
        "embedding": [0.1, 0.2, 0.3],
    }

    try:
        first_id = create_chunk(chunk)
        assert first_id is not None
        with pytest.raises(DuplicateKeyError):
            create_chunk(chunk)
    finally:
        mongodb.chunks_collection.delete_one({"chunk_id": "duplicate_test_chunk"})
        mongodb.close()


def test_document_repository_crud():
    mongodb.connect()
    test_file_hash = f"test_hash_{uuid.uuid4().hex}"
    test_document = {
        "type": "test",
        "project": "ManualMind",
        "message": "MongoDB CRUD test",
        "file_hash": test_file_hash,
    }
    document_id = None
    try:
        document_id = mongodb.insert_document(test_document)
        assert document_id is not None
        doc = mongodb.find_document(document_id)
        assert doc is not None
        assert doc["file_hash"] == test_file_hash
    finally:
        if document_id is not None:
            mongodb.collection.delete_one({"_id": document_id})
        mongodb.close()


# ---------------------------------------------------------------------------
# 5. End-to-End Ingestion Pipeline
# ---------------------------------------------------------------------------
def test_ingest_pdf(monkeypatch):
    sample_pages = [
        {"page_number": 1, "text": "Hydraulic filter maintenance procedure.", "images": []}
    ]
    sample_chunks = [
        {
            "chunk_id": "test_hash_page_1_chunk_1",
            "file_hash": "test_hash",
            "page_number": 1,
            "chunk_index": 1,
            "text": "Hydraulic filter maintenance procedure.",
            "images": [],
        }
    ]
    embedded_chunks = [{**sample_chunks[0], "embedding": [0.1, 0.2, 0.3]}]
    stored_chunks = []

    monkeypatch.setattr(ingestion_service, "calculate_file_hash", lambda p: "test_hash")
    monkeypatch.setattr(ingestion_service, "extract_text_and_images_from_pdf", lambda p, h: sample_pages)
    monkeypatch.setattr(ingestion_service, "create_page_chunks", lambda **kwargs: sample_chunks)
    monkeypatch.setattr(ingestion_service, "find_chunk_by_id", lambda cid: None)
    monkeypatch.setattr(ingestion_service, "embed_chunks", lambda chunks: embedded_chunks)
    monkeypatch.setattr(ingestion_service, "create_chunk", lambda c: stored_chunks.append(c) or "id_123")

    result = ingestion_service.ingest_pdf("test.pdf")
    assert result == {
        "file_hash": "test_hash",
        "total_pages": 1,
        "total_chunks": 1,
        "new_chunks": 1,
        "inserted_chunks": 1,
        "skipped_chunks": 0,
    }
    assert len(stored_chunks) == 1
    assert stored_chunks[0]["chunk_id"] == "test_hash_page_1_chunk_1"


def test_ingest_pdf_skips_existing_chunk(monkeypatch):
    sample_pages = [{"page_number": 1, "text": "Existing content.", "images": []}]
    sample_chunks = [{
        "chunk_id": "existing_hash_page_1_chunk_1",
        "file_hash": "existing_hash",
        "page_number": 1,
        "chunk_index": 1,
        "text": "Existing content.",
        "images": [],
    }]

    embedding_called = False

    def fake_embed(chunks):
        nonlocal embedding_called
        embedding_called = True
        return chunks

    monkeypatch.setattr(ingestion_service, "calculate_file_hash", lambda p: "existing_hash")
    monkeypatch.setattr(ingestion_service, "extract_text_and_images_from_pdf", lambda p, h: sample_pages)
    monkeypatch.setattr(ingestion_service, "create_page_chunks", lambda **kwargs: sample_chunks)
    monkeypatch.setattr(ingestion_service, "find_chunk_by_id", lambda cid: {"chunk_id": cid})
    monkeypatch.setattr(ingestion_service, "embed_chunks", fake_embed)

    result = ingestion_service.ingest_pdf("test.pdf")
    assert result["new_chunks"] == 0
    assert result["skipped_chunks"] == 1
    assert embedding_called is False
