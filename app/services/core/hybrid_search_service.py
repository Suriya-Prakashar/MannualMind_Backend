import logging
from typing import Any

from app.config import (
    KEYWORD_CANDIDATE_LIMIT,
    RRF_K,
    SEMANTIC_CANDIDATE_LIMIT,
)
from app.services.core.embedding_service import generate_embedding
from app.services.core.vector_search_service import search_similar_chunks
from app.services.repositories.chunk_repository import search_chunks_by_keyword

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    ranking_lists: list[list[dict[str, Any]]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Combine multiple ranked lists of chunks using Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_score(d) = sum(1.0 / (k + rank_i(d))) for all ranking lists i where d appears.
        (Using 1-based rank indexing)

    Deduplicates candidates by chunk_id, preserving all original chunk fields.
    Sorts descending by RRF score with deterministic tie-breaking.
    """
    if k < 1:
        raise ValueError("RRF smoothing constant k must be greater than 0.")

    scores: dict[str, float] = {}
    doc_map: dict[str, dict[str, Any]] = {}

    for ranking_list in ranking_lists:
        for rank, chunk in enumerate(ranking_list, start=1):
            if not isinstance(chunk, dict):
                continue

            chunk_id = str(chunk.get("chunk_id") or chunk.get("text", ""))
            if not chunk_id:
                continue

            scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

            if chunk_id not in doc_map:
                doc_map[chunk_id] = dict(chunk)

    fused_results: list[dict[str, Any]] = []
    for chunk_id, chunk_data in doc_map.items():
        chunk_copy = dict(chunk_data)
        chunk_copy["rrf_score"] = scores[chunk_id]
        fused_results.append(chunk_copy)

    # Deterministic sort: highest RRF score first, then alphabetically by chunk_id
    fused_results.sort(
        key=lambda item: (-item["rrf_score"], str(item.get("chunk_id", "")))
    )

    return fused_results


def search_semantic_branch(
    query_embedding: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Retrieve candidate chunks from Atlas Vector Search."""
    try:
        return search_similar_chunks(
            query_embedding=query_embedding,
            limit=limit,
        )
    except Exception as exc:
        logger.warning(
            "Semantic search branch failed: %s",
            exc.__class__.__name__,
        )
        return []


def search_keyword_branch(
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Retrieve candidate chunks using keyword search."""
    try:
        return search_chunks_by_keyword(
            query=query,
            limit=limit,
        )
    except Exception as exc:
        logger.warning(
            "Keyword search branch failed: %s",
            exc.__class__.__name__,
        )
        return []


def execute_hybrid_search(
    query: str,
    query_embedding: list[float] | None = None,
    semantic_limit: int = SEMANTIC_CANDIDATE_LIMIT,
    keyword_limit: int = KEYWORD_CANDIDATE_LIMIT,
    rrf_k: int = RRF_K,
) -> list[dict[str, Any]]:
    """
    Execute hybrid retrieval combining semantic vector search and keyword search.

    Branch failures are handled gracefully: if one branch fails, the other continues.
    Results are deduplicated and merged via Reciprocal Rank Fusion (RRF).
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    cleaned_query = query.strip()

    # 1. Semantic search branch
    semantic_results: list[dict[str, Any]] = []
    try:
        if query_embedding is None:
            query_embedding = generate_embedding(cleaned_query)

        semantic_results = search_semantic_branch(
            query_embedding=query_embedding,
            limit=semantic_limit,
        )
    except Exception as exc:
        logger.warning(
            "Semantic search execution failed: %s",
            exc.__class__.__name__,
        )

    # 2. Keyword search branch
    keyword_results: list[dict[str, Any]] = []
    try:
        keyword_results = search_keyword_branch(
            query=cleaned_query,
            limit=keyword_limit,
        )
    except Exception as exc:
        logger.warning(
            "Keyword search execution failed: %s",
            exc.__class__.__name__,
        )

    logger.info(
        "Hybrid search candidates: %d semantic, %d keyword",
        len(semantic_results),
        len(keyword_results),
    )

    # 3. Reciprocal Rank Fusion
    return reciprocal_rank_fusion(
        [semantic_results, keyword_results],
        k=rrf_k,
    )
