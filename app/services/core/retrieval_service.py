from app.services.core.embedding_service import (
    generate_embedding,
)
from app.services.core.vector_search_service import (
    search_similar_chunks,
)
from app.services.repositories.chunk_repository import (
    search_chunks_by_keyword,
)


def retrieve_chunks(
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Retrieve relevant chunks using semantic search."""

    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if limit < 1:
        raise ValueError("limit must be greater than 0.")

    cleaned_query = query.strip()

    try:
        query_embedding = generate_embedding(cleaned_query)

        results = search_similar_chunks(
            query_embedding=query_embedding,
            limit=limit,
        )

        if results:
            return results

    except Exception:
        # Fall back to keyword retrieval if semantic search fails.
        pass

    return search_chunks_by_keyword(
        query=cleaned_query,
        limit=limit,
    )