"""
Test Suite: RAG, Multimodal Diagrams, Session Memory, Streaming, Retry & Maintenance Tools
Consolidates and validates:
- Multimodal PDF diagram resolution & static URLs
- Answer generation with Gemini and fallback response
- Multi-turn session memory (last 5 turns injected into prompt)
- 3x Retry protection at 3s intervals for AI model calls
- Token-by-token streaming generator
- RFC email validation & authorized supplier directory
- Maintenance email draft, approval workflow, and SMTP dispatch
"""
from collections.abc import Generator
import time
from unittest.mock import MagicMock, call, patch
import pytest

from app.models.routing import RouteType
from app.models.session import ConversationTurn
from app.services.core.answer_generation_service import (
    FALLBACK_ANSWER,
    build_prompt,
    call_gemini_with_retry,
    format_context,
    generate_answer,
    generate_answer_stream,
)
from app.services.core.email_service import (
    EmailSendResult,
    is_valid_email_address,
    send_smtp_email,
    validate_supplier_recipient,
)
from app.services.core.image_resolver_service import (
    collect_unique_images_from_chunks,
    resolve_chunk_images,
)
from app.services.core.maintenance_email_service import (
    MaintenanceWorkflowState,
    clear_pending_requests,
    compute_draft_fingerprint,
    handle_maintenance_tool_query,
)
from app.services.core.query_service import (
    process_query,
    process_query_stream,
)
from app.services.core.session_service import session_service


@pytest.fixture(autouse=True)
def clean_state():
    session_service.clear_all_sessions()
    clear_pending_requests()
    yield
    session_service.clear_all_sessions()
    clear_pending_requests()


# ===========================================================================
# 1. Multimodal RAG with PDF Images
# ===========================================================================
def test_resolve_chunk_images_from_chunk_data():
    chunk = {
        "chunk_id": "chunk_mb_01",
        "file_hash": "hash_abc",
        "page_number": 18,
        "images": [
            {
                "image_id": "page_18_image_1",
                "filename": "page_18_image_1.png",
                "path": "data/extracted/hash_abc/images/page_18_image_1.png",
            }
        ],
    }
    resolved = resolve_chunk_images(chunk)
    assert len(resolved) == 1
    assert resolved[0]["image_id"] == "page_18_image_1"
    assert resolved[0]["page_number"] == 18
    assert resolved[0]["url"] == "/static/images/hash_abc/images/page_18_image_1.png"


def test_collect_unique_images_from_chunks():
    chunks = [
        {
            "file_hash": "hash_xyz",
            "page_number": 10,
            "images": [
                {"image_id": "img_1", "filename": "fan.png"},
                {"image_id": "img_2", "filename": "screw.png"},
            ],
        },
        {
            "file_hash": "hash_xyz",
            "page_number": 10,
            "images": [
                {"image_id": "img_1", "filename": "fan.png"},
            ],
        },
    ]
    unique = collect_unique_images_from_chunks(chunks)
    assert len(unique) == 2
    filenames = [u["filename"] for u in unique]
    assert "fan.png" in filenames
    assert "screw.png" in filenames


def test_format_context_includes_image_references():
    chunks = [
        {
            "chunk_id": "chk_101",
            "file_hash": "hash_demo",
            "page_number": 22,
            "text": "Step 1: Disconnect the motherboard cable.",
            "images": [{"image_id": "img_mb", "filename": "motherboard_cable.jpeg"}],
        }
    ]
    context = format_context(chunks)
    assert "Associated Diagrams/Figures" in context
    assert "motherboard_cable.jpeg" in context
    assert "/static/images/hash_demo/images/motherboard_cable.jpeg" in context


# ===========================================================================
# 2. Multi-Turn Session Memory (5 Turns)
# ===========================================================================
def test_session_service_turn_tracking():
    sess = session_service.get_or_create_session("sess_turn_test")
    assert sess.session_id == "sess_turn_test"

    for i in range(1, 8):
        session_service.add_turn(
            session_id="sess_turn_test",
            user_query=f"Query {i}",
            assistant_response=f"Answer {i}",
            route=RouteType.RAG,
        )

    recent = session_service.get_recent_history("sess_turn_test", limit=5)
    assert len(recent) == 5
    assert recent[0].user_query == "Query 3"
    assert recent[-1].user_query == "Query 7"


def test_prompt_includes_last_5_turns():
    history = [
        ConversationTurn(user_query=f"Q{i}", assistant_response=f"Ans{i}", route=RouteType.RAG)
        for i in range(1, 8)
    ]
    prompt = build_prompt(
        question="How do I fix it?",
        context="Context details",
        conversation_history=history,
    )
    assert "--- RECENT CONVERSATION HISTORY (Last 5 Turns) ---" in prompt
    assert "User: Q3" in prompt
    assert "User: Q7" in prompt
    assert "User: Q1" not in prompt


# ===========================================================================
# 3. Resilience: 3x Retry Protection (3s interval)
# ===========================================================================
def test_call_gemini_with_retry_success_first_try():
    mock_func = MagicMock(return_value="Success")
    result = call_gemini_with_retry(mock_func, max_retries=3, retry_delay=0.01)
    assert result == "Success"
    assert mock_func.call_count == 1


def test_call_gemini_with_retry_recovers_on_second_attempt():
    mock_func = MagicMock(side_effect=[Exception("Transient error"), "Success on 2nd"])
    with patch("time.sleep") as mock_sleep:
        result = call_gemini_with_retry(mock_func, max_retries=3, retry_delay=3.0)
    assert result == "Success on 2nd"
    assert mock_func.call_count == 2
    mock_sleep.assert_called_once_with(3.0)


def test_call_gemini_with_retry_fails_after_3_attempts():
    mock_func = MagicMock(side_effect=Exception("Permanent failure"))
    with patch("time.sleep") as mock_sleep, pytest.raises(RuntimeError) as exc_info:
        call_gemini_with_retry(mock_func, max_retries=3, retry_delay=3.0)
    assert "after 3 attempts" in str(exc_info.value)
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2


# ===========================================================================
# 4. Streaming Generator
# ===========================================================================
def test_generate_answer_stream():
    mock_chunk1 = MagicMock(text="Step ")
    mock_chunk2 = MagicMock(text="1: Complete.")
    mock_stream = [mock_chunk1, mock_chunk2]

    chunks = [{"chunk_id": "c1", "text": "Procedure"}]
    with patch("app.services.core.answer_generation_service.client.models.generate_content_stream", return_value=mock_stream):
        tokens = list(generate_answer_stream("How to repair?", chunks))

    assert tokens == ["Step ", "1: Complete."]


# ===========================================================================
# 5. Email Service & Maintenance Tool Workflow
# ===========================================================================
def test_email_validation():
    assert is_valid_email_address("technician@manualmind.ai") is True
    assert is_valid_email_address("invalid-email") is False
    assert is_valid_email_address("") is False


def test_validate_supplier_recipient():
    is_valid, is_auth, msg = validate_supplier_recipient("parts-support@samsung-authorized.com")
    assert is_valid is True
    assert is_auth is True
    assert "Samsung Authorised Parts Centre" in msg


def test_send_smtp_email_mocked():
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_instance

        with patch("app.services.core.email_service.SMTP_HOST", "smtp.test.com"):
            result = send_smtp_email(
                recipient="parts@supplier.com",
                subject="Spare part quote",
                body="Please provide quote for fan.",
            )

        assert result.success is True
        assert result.provider_message_id is not None
        assert mock_instance.send_message.called


def test_maintenance_tool_approval_workflow():
    # 1. Draft request
    query = "Send maintenance email to parts@supplier.com for broken motherboard on Samsung NP740"
    res1 = handle_maintenance_tool_query(query)
    assert res1.status == MaintenanceWorkflowState.DRAFT_READY
    assert res1.requires_user_approval is True
    assert res1.request_id is not None
    req_id = res1.request_id


    # 2. Approve request
    with patch("app.services.core.maintenance_email_service.send_smtp_email") as mock_send:
        mock_send.return_value = EmailSendResult(
            success=True,
            provider_message_id="msg_999",
            status_message="Sent",
        )
        res2 = handle_maintenance_tool_query(f"APPROVE {req_id}")

    assert res2.status == MaintenanceWorkflowState.SENT
    assert res2.requires_user_approval is False
    assert "msg_999" in res2.message
