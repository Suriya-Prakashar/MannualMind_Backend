import logging

from google import genai

from app.config import (
    GEMINI_API_KEY,
    GEMINI_GENERATION_MODEL,
)

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "I cannot find this information in the provided manual."
)

client = genai.Client(
    api_key=GEMINI_API_KEY
)


def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into structured context with page numbers and chunk IDs."""
    context_blocks = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "unknown")
        page_number = chunk.get("page_number", "N/A")
        text = chunk.get("text", "").strip()
        context_blocks.append(
            f"[Source Chunk ID: {chunk_id} | Page: {page_number}]\n{text}"
        )
    return "\n\n".join(context_blocks)


def build_prompt(question: str, context: str) -> str:
    """Build a prompt instructing the model to ground its answer strictly in the provided context."""
    return (
        "You are ManualMind, an AI assistant for technical manuals.\n"
        "Your task is to answer the user's question using ONLY the provided manual context below.\n\n"
        "Rules:\n"
        "1. Answer strictly based on the provided context.\n"
        "2. Do not assume or invent facts, procedures, or specifications not in the text.\n"
        f"3. If the context does not contain enough information to answer the question, respond with exactly: \"{FALLBACK_ANSWER}\"\n"
        "4. Accurately preserve technical details such as model numbers, measurements, units, error codes, and safety warnings.\n\n"
        f"--- CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
        f"Question: {question.strip()}\nAnswer:"
    )


def generate_answer(
    question: str,
    chunks: list[dict],
) -> str:
    """Generate a grounded natural-language answer using Gemini and retrieved chunks."""
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not chunks:
        return FALLBACK_ANSWER

    context = format_context(chunks)
    prompt = build_prompt(question, context)

    try:
        response = client.models.generate_content(
            model=GEMINI_GENERATION_MODEL,
            contents=prompt,
        )

        if not response or not response.text:
            return FALLBACK_ANSWER

        answer = response.text.strip()
        return answer if answer else FALLBACK_ANSWER

    except Exception as exc:
        logger.error(
            "Answer generation failed: %s",
            exc.__class__.__name__,
        )
        raise RuntimeError(
            f"Failed to generate answer from manual context: {exc}"
        ) from exc
