
from unittest.mock import patch

import pytest

from app.services.core.retrieval_service import retrieve_chunks


def test_retrieve_chunks_success():
    expected = [
        {
            "chunk_id": "chunk_001",
            "file_hash": "abc123",
            "page_number": 2,
            "text": "Replace the hydraulic filter regularly.",
        }
    ]

    with patch(
        "app.services.core.retrieval_service.search_chunks_by_keyword",
        return_value=expected,
    ) as mock_search:
        result = retrieve_chunks("hydraulic filter")

    assert result == expected
    mock_search.assert_called_once_with(
        query="hydraulic filter",
        limit=5,
    )


def test_retrieve_chunks_empty_query():
    with pytest.raises(ValueError):
        retrieve_chunks("   ")