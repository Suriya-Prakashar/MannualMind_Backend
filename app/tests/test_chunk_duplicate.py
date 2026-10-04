import pytest
from pymongo.errors import DuplicateKeyError

from app.database import mongodb
from app.services.chunk_repository import create_chunk


def test_duplicate_chunk_is_rejected():

    mongodb.connect()

    chunk = {
        "chunk_id": "duplicate_test_chunk",
        "file_hash": "duplicate_test_file",
        "page_number": 1,
        "chunk_index": 1,
        "text": "Duplicate chunk test",
        "images": [],
        "embedding": [
            0.1,
            0.2,
            0.3,
        ],
    }

    try:

        # First insertion should succeed
        first_id = create_chunk(chunk)

        assert first_id is not None

        # Second insertion with the same chunk_id
        # must be rejected by MongoDB
        with pytest.raises(DuplicateKeyError):
            create_chunk(chunk)

    finally:

        mongodb.chunks_collection.delete_one(
            {
                "chunk_id": "duplicate_test_chunk"
            }
        )

        mongodb.close()