from unittest.mock import MagicMock, patch
import pytest

from app.services.core.answer_generation_service import (
    FALLBACK_ANSWER,
    build_prompt,
    format_context,
    generate_answer,
)


def test_format_context_includes_metadata_and_text():
    chunks = [
        {
            "chunk_id": "chunk_001",
            "page_number": 4,
            "text": "Tighten the oil drain bolt to 30 Nm.",
        },
        {
            "chunk_id": "chunk_002",
            "page_number": 5,
            "text": "Check for oil leaks after engine run.",
        },
    ]

    formatted = format_context(chunks)
    assert "[Source Chunk ID: chunk_001 | Page: 4]" in formatted
    assert "Tighten the oil drain bolt to 30 Nm." in formatted
    assert "[Source Chunk ID: chunk_002 | Page: 5]" in formatted
    assert "Check for oil leaks after engine run." in formatted


def test_build_prompt_contains_rules_and_context():
    context = "[Source Chunk ID: chunk_001 | Page: 4]\nTighten bolt to 30 Nm."
    prompt = build_prompt("What torque is needed?", context)

    assert "You are ManualMind" in prompt
    assert "What torque is needed?" in prompt
    assert "Tighten bolt to 30 Nm." in prompt
    assert FALLBACK_ANSWER in prompt


def test_generate_answer_empty_chunks_returns_fallback_without_api_call():
    with patch(
        "app.services.core.answer_generation_service.client.models.generate_content"
    ) as mock_generate:
        result = generate_answer("What is the oil capacity?", [])

    assert result == FALLBACK_ANSWER
    mock_generate.assert_not_called()


def test_generate_answer_empty_question_raises_value_error():
    with pytest.raises(ValueError, match="Question cannot be empty."):
        generate_answer("", [{"chunk_id": "c1", "text": "sample"}])

    with pytest.raises(ValueError, match="Question cannot be empty."):
        generate_answer("   ", [{"chunk_id": "c1", "text": "sample"}])


def test_generate_answer_successful_call():
    chunks = [
        {
            "chunk_id": "c_12",
            "page_number": 12,
            "text": "Engine oil capacity is 4.5 liters for Model X.",
        }
    ]

    mock_response = MagicMock()
    mock_response.text = "The engine oil capacity is 4.5 liters for Model X."

    with patch(
        "app.services.core.answer_generation_service.client.models.generate_content",
        return_value=mock_response,
    ) as mock_generate:
        answer = generate_answer("What is the oil capacity?", chunks)

    assert answer == "The engine oil capacity is 4.5 liters for Model X."
    mock_generate.assert_called_once()
    call_kwargs = mock_generate.call_args.kwargs
    assert "What is the oil capacity?" in call_kwargs["contents"]
    assert "c_12" in call_kwargs["contents"]
    assert "Page: 12" in call_kwargs["contents"]


def test_generate_answer_empty_model_response():
    chunks = [{"chunk_id": "c_1", "page_number": 1, "text": "Some text."}]

    mock_response = MagicMock()
    mock_response.text = ""

    with patch(
        "app.services.core.answer_generation_service.client.models.generate_content",
        return_value=mock_response,
    ):
        answer = generate_answer("Unknown question", chunks)

    assert answer == FALLBACK_ANSWER


def test_generate_answer_api_error_raises_runtime_error():
    chunks = [{"chunk_id": "c_1", "page_number": 1, "text": "Some text."}]

    with patch(
        "app.services.core.answer_generation_service.client.models.generate_content",
        side_effect=Exception("API quota exceeded"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Failed to generate answer from manual context",
        ):
            generate_answer("What is the oil capacity?", chunks)
