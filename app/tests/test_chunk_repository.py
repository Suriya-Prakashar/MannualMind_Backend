import uuid

from app.database import mongodb
from app.services.chunk_repository import (
    create_chunk,
    create_chunks,
    find_chunk_by_id,
)


def test_chunk_repository():

    mongodb.connect()

    chunk_id = (
        f"test_chunk_{uuid.uuid4().hex}"
    )

    chunk = {
        "chunk_id": chunk_id,
        "file_hash": "test_file_hash",
        "page_number": 1,
        "chunk_index": 1,
        "text": "Hydraulic filter maintenance",
        "images": [],
        "embedding": [
            0.1,
            0.2,
            0.3,
        ],
    }

    try:
        inserted_id = create_chunk(chunk)

        assert inserted_id is not None

        stored_chunk = find_chunk_by_id(
            chunk_id
        )

        assert stored_chunk is not None
        assert stored_chunk["chunk_id"] == chunk_id
        assert stored_chunk["text"] == (
            "Hydraulic filter maintenance"
        )
        assert stored_chunk["embedding"] == [
            0.1,
            0.2,
            0.3,
        ]

    finally:
        mongodb.chunks_collection.delete_one(
            {
                "chunk_id": chunk_id
            }
        )

        mongodb.close()