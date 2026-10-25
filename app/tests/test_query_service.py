from unittest.mock import patch
import pytest

from app.services.core.query_service import process_query


def test_process_query_success_with_results():
    mock_chunks = [
        {
            "chunk_id": "chunk_001",
            "file_hash": "abc123",
            "page_number": 2,
            "text": "The engine oil capacity is 4 litres.",
        }
    ]

    with patch(
        "app.services.core.query_service.retrieve_chunks",
        return_value=mock_chunks,
    ) as mock_retrieve:
        response = process_query("  What is the engine oil capacity?  ")

    assert response == {
        "query": "What is the engine oil capacity?",
        "message": "Matching manual chunks retrieved.",
        "status": "success",
        "results": mock_chunks,
    }
    mock_retrieve.assert_called_once_with("What is the engine oil capacity?")


def test_process_query_no_results():
    with patch(
        "app.services.core.query_service.retrieve_chunks",
        return_value=[],
    ) as mock_retrieve:
        response = process_query("What is unknown?")

    assert response == {
        "query": "What is unknown?",
        "message": "No matching manual chunks found.",
        "status": "success",
        "results": [],
    }
    mock_retrieve.assert_called_once_with("What is unknown?")


def test_process_query_empty_string():
    with pytest.raises(ValueError, match="Query cannot be empty."):
        process_query("")


def test_process_query_whitespace_string():
    with pytest.raises(ValueError, match="Query cannot be empty."):
        process_query("   ")