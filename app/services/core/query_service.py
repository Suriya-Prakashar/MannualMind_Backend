from app.services.core.answer_generation_service import (
    FALLBACK_ANSWER,
    generate_answer,
)
from app.services.core.retrieval_service import retrieve_chunks


def process_query(query: str) -> dict:
    """Process a user query, retrieve relevant manual chunks, and generate a grounded answer."""
    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    chunks = retrieve_chunks(cleaned_query)

    if not chunks:
        return {
            "query": cleaned_query,
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "status": "success",
            "message": "No matching manual chunks found.",
        }

    answer = generate_answer(cleaned_query, chunks)

    sources = [
        {
            "chunk_id": chunk.get("chunk_id", ""),
            "page_number": chunk.get("page_number", 0),
            "snippet": chunk.get("text", "").strip(),
        }
        for chunk in chunks
    ]

    return {
        "query": cleaned_query,
        "answer": answer,
        "sources": sources,
        "status": "success",
        "message": "Answer generated successfully.",
    }