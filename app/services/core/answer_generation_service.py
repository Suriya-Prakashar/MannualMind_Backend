from collections.abc import Generator
import logging
import time
from typing import Any, Optional

from google import genai

from app.config import (
    GEMINI_API_KEY,
    GEMINI_GENERATION_MODEL,
)
from app.services.core.image_resolver_service import resolve_chunk_images

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "I cannot find this information in the provided manual."
)

RETRY_MAX_ATTEMPTS = 3
RETRY_INTERVAL_SECONDS = 3.0

client = genai.Client(
    api_key=GEMINI_API_KEY
)


def call_gemini_with_retry(
    func: Any,
    max_retries: int = RETRY_MAX_ATTEMPTS,
    retry_delay: float = RETRY_INTERVAL_SECONDS,
) -> Any:
    """
    Execute a Gemini model call with up to 3 retries at 3-second intervals.
    Catches transient exceptions (rate limits, network timeouts, API errors).
    """
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Gemini API call failed on attempt %d/%d: %s. Retrying in %.1f seconds...",
                attempt,
                max_retries,
                exc,
                retry_delay,
            )
            if attempt < max_retries:
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Failed to generate answer from manual context after {max_retries} attempts: {last_exc}"
    ) from last_exc


def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into structured context with page numbers, chunk IDs, and associated figures."""
    context_blocks = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "unknown")
        page_number = chunk.get("page_number", "N/A")
        text = chunk.get("text", "").strip()

        images = resolve_chunk_images(chunk)
        image_info = ""
        if images:
            img_refs = [
                f"[Figure on Page {img['page_number']}: {img['filename']} | URL: {img.get('url', '')}]"
                for img in images
            ]
            image_info = f"\nAssociated Diagrams/Figures: {', '.join(img_refs)}"

        context_blocks.append(
            f"[Source Chunk ID: {chunk_id} | Page: {page_number}]{image_info}\n{text}"
        )
    return "\n\n".join(context_blocks)


def build_prompt(
    question: str,
    context: str,
    conversation_history: Optional[list[Any]] = None,
) -> str:
    """
    Build a grounded prompt with manual context, multimodal image guidance,
    and recent multi-turn conversation memory (last 5 turns).
    """
    history_section = ""
    if conversation_history:
        history_lines = []
        for turn in conversation_history[-5:]:
            u_q = getattr(turn, "user_query", None) or (turn.get("user_query") if isinstance(turn, dict) else None)
            a_r = getattr(turn, "assistant_response", None) or (turn.get("assistant_response") if isinstance(turn, dict) else None)
            if u_q:
                history_lines.append(f"User: {u_q}")
            if a_r:
                first_summary = a_r.strip().splitlines()[0]
                history_lines.append(f"Assistant: {first_summary}")
        if history_lines:
            history_section = (
                f"--- RECENT CONVERSATION HISTORY (Last 5 Turns) ---\n"
                + "\n".join(history_lines)
                + "\n--- END CONVERSATION HISTORY ---\n\n"
            )

    return (
        "You are ManualMind, an AI assistant for technical manuals.\n"
        "Your task is to answer the user's question using ONLY the provided manual context below.\n\n"
        "Rules:\n"
        "1. Answer strictly based on the provided context.\n"
        "2. Do not assume or invent facts, procedures, or specifications not in the text.\n"
        f"3. If the context does not contain enough information to answer the question, respond with exactly: \"{FALLBACK_ANSWER}\"\n"
        "4. Accurately preserve technical details such as model numbers, measurements, units, error codes, and safety warnings.\n"
        "5. If step-by-step procedures refer to diagrams or figures from the manual, cite the corresponding figure or diagram URL.\n\n"
        f"{history_section}"
        f"--- CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
        f"Question: {question.strip()}\nAnswer:"
    )


def generate_answer(
    question: str,
    chunks: list[dict],
    conversation_history: Optional[list[Any]] = None,
) -> str:
    """
    Generate a grounded natural-language answer using Gemini and retrieved chunks,
    with 3-attempt 3-second retry resilience and conversation history memory.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not chunks:
        return FALLBACK_ANSWER

    context = format_context(chunks)
    prompt = build_prompt(question, context, conversation_history=conversation_history)

    def _call():
        response = client.models.generate_content(
            model=GEMINI_GENERATION_MODEL,
            contents=prompt,
        )
        if not response or not response.text:
            return FALLBACK_ANSWER
        answer = response.text.strip()
        return answer if answer else FALLBACK_ANSWER

    return call_gemini_with_retry(_call)


def generate_answer_stream(
    question: str,
    chunks: list[dict],
    conversation_history: Optional[list[Any]] = None,
) -> Generator[str, None, None]:
    """
    Stream answer tokens word-by-word / chunk-by-chunk using Gemini streaming API,
    with 3-attempt 3-second retry resilience.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not chunks:
        yield FALLBACK_ANSWER
        return

    context = format_context(chunks)
    prompt = build_prompt(question, context, conversation_history=conversation_history)

    def _call_stream():
        return client.models.generate_content_stream(
            model=GEMINI_GENERATION_MODEL,
            contents=prompt,
        )

    response_stream = call_gemini_with_retry(_call_stream)
    for chunk in response_stream:
        if chunk and chunk.text:
            yield chunk.text
