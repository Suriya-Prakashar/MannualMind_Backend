import logging
import re

from app.config import RETRIEVAL_TOP_K
from app.services.core.hybrid_search_service import execute_hybrid_search
from app.services.core.image_resolver_service import resolve_chunk_images
from app.services.core.reranking_service import rerank_chunks
from app.services.repositories.chunk_repository import search_chunks_by_keyword

logger = logging.getLogger(__name__)

STOPWORDS = {
    "what", "is", "the", "how", "to", "in", "on", "a", "an", "for", "of",
    "and", "does", "do", "can", "you", "my", "this", "that", "it", "with",
}


def _extract_fallback_terms(query: str) -> str:
    """Extract substantive search terms by removing common conversational stopwords."""
    words = re.findall(r"\b[a-zA-Z0-9_\-]+\b", query.lower())
    substantive = [w for w in words if w not in STOPWORDS and len(w) > 1]
    return " ".join(substantive) if substantive else query


def retrieve_chunks(
    query: str,
    limit: int = RETRIEVAL_TOP_K,
) -> list[dict]:
    """
    Retrieve relevant chunks using hybrid search (semantic + keyword with RRF)
    with multi-tier fallback (relaxed term search fallback) and image resolution.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if limit < 1:
        raise ValueError("limit must be greater than 0.")

    cleaned_query = query.strip()

    # 1. Primary retrieval: Hybrid search (Vector + Keyword fused via RRF)
    try:
        candidates = execute_hybrid_search(cleaned_query)
    except Exception as exc:
        logger.warning("Hybrid search execution encountered error: %s", exc)
        candidates = []

    # 2. Fallback Tier 1: Relaxed keyword search if hybrid search yielded 0 candidates
    if not candidates:
        fallback_query = _extract_fallback_terms(cleaned_query)
        if fallback_query and fallback_query != cleaned_query:
            logger.info("Executing retrieval fallback with relaxed query: '%s'", fallback_query)
            try:
                candidates = search_chunks_by_keyword(fallback_query, limit=limit * 2)
            except Exception as fb_exc:
                logger.warning("Fallback keyword search failed: %s", fb_exc)
                candidates = []

    if not candidates:
        return []

    # 3. Rerank candidates based on relevance to original query
    reranked = rerank_chunks(
        query=cleaned_query,
        candidates=candidates,
        top_k=limit,
    )

    # 4. Resolve image metadata for each retrieved chunk
    for chunk in reranked:
        chunk["images"] = resolve_chunk_images(chunk)

    return reranked