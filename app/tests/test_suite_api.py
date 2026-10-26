"""
Test Suite: API Endpoints (Synchronous & Streaming)
Consolidates and validates:
- POST /query/ (RAG, DIRECT, TOOL, CLARIFY routes)
- POST /query/stream (Server-Sent Events streaming)
- Validation, error handling (400, 422, 502)
"""
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
        "route": "RAG",
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


def test_query_api_direct_route():
    mock_response = {
        "query": "hello my frnd",
        "route": "DIRECT",
        "answer": "Hello! I am ManualMind, your technical manual assistant.",
        "sources": [],
        "status": "success",
        "message": "Direct response generated.",
    }

    with patch(
        "app.api.query.process_query",
        return_value=mock_response,
    ) as mock_process:
        response = client.post(
            "/query/",
            json={"query": "hello my frnd"},
        )

    assert response.status_code == 200
    assert response.json() == mock_response
    mock_process.assert_called_once_with("hello my frnd")


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


def test_query_api_maintenance_tool_route():
    mock_response = {
        "query": "Send maintenance email to parts@example.com for broken motor",
        "route": "TOOL",
        "answer": "Maintenance enquiry email draft has been prepared.",
        "sources": [],
        "status": "success",
        "message": "Maintenance tool status: DRAFT_READY",
        "tool_result": {
            "status": "DRAFT_READY",
            "request_id": "req_12345",
            "requires_user_approval": True,
        },
    }

    with patch(
        "app.api.query.process_query",
        return_value=mock_response,
    ):
        response = client.post(
            "/query/",
            json={"query": "Send maintenance email to parts@example.com for broken motor"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "TOOL"
    assert "tool_result" in data
    assert data["tool_result"]["request_id"] == "req_12345"
    assert data["tool_result"]["requires_user_approval"] is True


def test_query_api_with_session_and_clarify():
    mock_response = {
        "query": "it is not working",
        "route": "CLARIFY",
        "primary_route": "CLARIFY",
        "intent": "troubleshooting",
        "answer": "Could you please specify which machine or device you need assistance with?",
        "clarification_question": "Could you please specify which machine or device you need assistance with?",
        "missing_information": ["equipment_name_or_model"],
        "sources": [],
        "status": "success",
        "message": "Clarification required from user.",
        "session_id": "sess_api_test",
    }

    with patch(
        "app.api.query.process_query",
        return_value=mock_response,
    ) as mock_process:
        response = client.post(
            "/query/",
            json={"query": "it is not working", "session_id": "sess_api_test"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "CLARIFY"
    assert data["session_id"] == "sess_api_test"
    assert data["clarification_question"] == mock_response["clarification_question"]
    assert data["missing_information"] == ["equipment_name_or_model"]
    mock_process.assert_called_once_with("it is not working", session_id="sess_api_test")


def test_query_stream_api_endpoint_sse():
    mock_chunks = [
        {"chunk_id": "chk_api", "file_hash": "h_api", "page_number": 1, "text": "Manual info"}
    ]
    with patch("app.services.core.query_service.retrieve_chunks", return_value=mock_chunks), \
         patch("app.services.core.query_service.generate_answer_stream", return_value=iter(["Step ", "1: ", "Done."])):
        response = client.post(
            "/query/stream",
            json={"query": "What is the procedure for repair?"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body_text = response.text
    assert "event: metadata" in body_text
    assert "event: token" in body_text
    assert "event: done" in body_text
    assert "Step " in body_text
