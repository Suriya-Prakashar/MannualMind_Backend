from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_api_success():
    expected_sources = [
        {
            "chunk_id": "chunk_001",
            "page_number": 2,
            "snippet": "The engine oil capacity is 4 litres.",
        }
    ]

    mock_response = {
        "query": "What is the engine oil capacity?",
        "answer": "The engine oil capacity is 4 litres.",
        "sources": expected_sources,
        "status": "success",
        "message": "Answer generated successfully.",
    }

    with patch(
        "app.api.query.process_query",
        return_value=mock_response,
    ) as mock_process:
        response = client.post(
            "/query/",
            json={"query": "What is the engine oil capacity?"},
        )

    assert response.status_code == 200
    assert response.json() == mock_response
    mock_process.assert_called_once_with(
        "What is the engine oil capacity?"
    )


def test_query_api_empty_string():
    response = client.post(
        "/query/",
        json={"query": ""}
    )

    assert response.status_code == 422


def test_query_api_missing_query():
    response = client.post(
        "/query/",
        json={}
    )

    assert response.status_code == 422


def test_query_api_invalid_payload():
    response = client.post(
        "/query/",
        json={"query": 123}
    )

    assert response.status_code == 422


def test_query_api_value_error():
    with patch(
        "app.api.query.process_query",
        side_effect=ValueError("Invalid query parameter"),
    ):
        response = client.post(
            "/query/",
            json={"query": "What is the engine oil capacity?"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid query parameter"}


def test_query_api_runtime_error():
    with patch(
        "app.api.query.process_query",
        side_effect=RuntimeError("Model generation failed"),
    ):
        response = client.post(
            "/query/",
            json={"query": "What is the engine oil capacity?"},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "Model generation failed"}