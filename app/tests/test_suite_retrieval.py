"""
Test Suite: Hybrid Search, Embeddings, Reranking & Retrieval Fallback
Consolidates and validates:
- Embedding dimensions and validation
- Batch chunk embedding
- Reciprocal Rank Fusion (RRF) math and metadata preservation
- Robust hybrid retrieval with branch failure resilience
- Bounded reranking with Gemini & graceful fallback
- Retrieval fallback for zero-result queries
"""
from unittest.mock import MagicMock, patch
import pytest

from app.services.core import chunk_embedding_service
from app.services.core.embedding_service import (
    EMBEDDING_DIMENSION,
    generate_embedding,
)
from app.services.core.hybrid_search_service import (
    execute_hybrid_search,
    reciprocal_rank_fusion,
)
from app.services.core.reranking_service import (
    build_rerank_prompt,
    parse_ranked_indices,
    rerank_chunks,
)
from app.services.core.retrieval_service import (
    _extract_fallback_terms,
    retrieve_chunks,
)


# ---------------------------------------------------------------------------
# 1. Embeddings
# ---------------------------------------------------------------------------
def test_generate_embedding_rejects_empty_text():
    with pytest.raises(ValueError, match="Text cannot be empty"):
        generate_embedding("")


def test_embedding_dimension_constant():
    assert EMBEDDING_DIMENSION == 768


def test_embed_chunks(monkeypatch):
    monkeypatch.setattr(
        chunk_embedding_service,
        "generate_embedding",
        lambda text: [0.1, 0.2, 0.3],
    )
    chunks = [
        {
            "chunk_id": "test_page_1_chunk_1",
            "file_hash": "test_hash",
            "page_number": 1,
            "chunk_index": 1,
            "text": "Hydraulic filter maintenance",
            "images": [],
        },
        {
            "chunk_id": "test_page_1_chunk_2",
            "file_hash": "test_hash",
            "page_number": 1,
            "chunk_index": 2,
            "text": "",
            "images": [],
        },
    ]
    embedded_chunks = chunk_embedding_service.embed_chunks(chunks)
    assert len(embedded_chunks) == 1
    assert embedded_chunks[0]["chunk_id"] == "test_page_1_chunk_1"
    assert embedded_chunks[0]["embedding"] == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# 2. Reciprocal Rank Fusion (RRF) & Hybrid Search
# ---------------------------------------------------------------------------
def test_rrf_single_list_score():
    list_a = [
        {"chunk_id": "c1", "text": "Chunk 1 text", "page_number": 1},
        {"chunk_id": "c2", "text": "Chunk 2 text", "page_number": 2},
    ]
    fused = reciprocal_rank_fusion([list_a], k=60)
    assert len(fused) == 2
    assert fused[0]["chunk_id"] == "c1"
    assert fused[1]["chunk_id"] == "c2"
    assert pytest.approx(fused[0]["rrf_score"], rel=1e-5) == 1.0 / 61.0
    assert pytest.approx(fused[1]["rrf_score"], rel=1e-5) == 1.0 / 62.0


def test_rrf_accumulates_scores_across_lists():
    list_a = [
        {"chunk_id": "c1", "text": "Chunk 1", "page_number": 1},
        {"chunk_id": "c2", "text": "Chunk 2", "page_number": 2},
    ]
    list_b = [
        {"chunk_id": "c2", "text": "Chunk 2", "page_number": 2},
        {"chunk_id": "c3", "text": "Chunk 3", "page_number": 3},
    ]
    fused = reciprocal_rank_fusion([list_a, list_b], k=60)
    assert len(fused) == 3
    assert fused[0]["chunk_id"] == "c2"
    assert fused[1]["chunk_id"] == "c1"
    assert fused[2]["chunk_id"] == "c3"
    expected_c2_score = (1.0 / 62.0) + (1.0 / 61.0)
    assert pytest.approx(fused[0]["rrf_score"], rel=1e-5) == expected_c2_score


def test_rrf_deduplication_preserves_metadata():
    list_a = [
        {
            "chunk_id": "model_np740",
            "file_hash": "hash_123",
            "page_number": 12,
            "text": "Model NP740 technical specifications",
        }
    ]
    list_b = [
        {
            "chunk_id": "model_np740",
            "file_hash": "hash_123",
            "page_number": 12,
            "text": "Model NP740 technical specifications",
        }
    ]
    fused = reciprocal_rank_fusion([list_a, list_b], k=60)
    assert len(fused) == 1
    assert fused[0]["file_hash"] == "hash_123"
    assert fused[0]["page_number"] == 12


def test_execute_hybrid_search_branch_resilience():
    # If semantic branch fails, keyword branch should still return results
    with patch(
        "app.services.core.hybrid_search_service.search_semantic_branch",
        return_value=[],
    ), patch(
        "app.services.core.hybrid_search_service.search_keyword_branch",
        return_value=[{"chunk_id": "kw1", "text": "Keyword result"}],
    ), patch(
        "app.services.core.hybrid_search_service.generate_embedding",
        return_value=[0.1] * 768,
    ):
        results = execute_hybrid_search("cooling fan")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "kw1"


# ---------------------------------------------------------------------------
# 3. Reranking Service
# ---------------------------------------------------------------------------
def test_parse_ranked_indices_valid():
    indices = parse_ranked_indices("[2, 1, 3]", 3)
    assert indices == [2, 1, 3]


def test_parse_ranked_indices_with_text():
    indices = parse_ranked_indices("Here are rankings: [3, 1, 2]", 3)
    assert indices == [3, 1, 2]


def test_parse_ranked_indices_fallback():
    indices = parse_ranked_indices("invalid response format", 3)
    assert indices == [1, 2, 3]


def test_rerank_chunks_single_candidate_bypasses_model():
    candidate = [{"chunk_id": "c1", "text": "Solo candidate"}]
    with patch("app.services.core.reranking_service.client") as mock_client:
        results = rerank_chunks("query", candidate)
    assert results == candidate
    mock_client.models.generate_content.assert_not_called()


def test_rerank_chunks_reorders_correctly():
    candidates = [
        {"chunk_id": "c1", "text": "First chunk"},
        {"chunk_id": "c2", "text": "Second chunk"},
        {"chunk_id": "c3", "text": "Third chunk"},
    ]
    mock_response = MagicMock()
    mock_response.text = "[2, 3, 1]"

    with patch(
        "app.services.core.reranking_service.client.models.generate_content",
        return_value=mock_response,
    ):
        reranked = rerank_chunks("query", candidates, top_k=3)

    assert [c["chunk_id"] for c in reranked] == ["c2", "c3", "c1"]


# ---------------------------------------------------------------------------
# 4. Retrieval Service & Fallback
# ---------------------------------------------------------------------------
def test_retrieve_chunks_success():
    mock_candidates = [
        {
            "chunk_id": "chunk_001",
            "file_hash": "abc123",
            "page_number": 2,
            "text": "Replace the hydraulic filter regularly.",
            "rrf_score": 0.032,
        }
    ]
    with patch(
        "app.services.core.retrieval_service.execute_hybrid_search",
        return_value=mock_candidates,
    ), patch(
        "app.services.core.retrieval_service.rerank_chunks",
        return_value=mock_candidates,
    ):
        result = retrieve_chunks("hydraulic filter", limit=5)

    assert len(result) == 1
    assert result[0]["chunk_id"] == "chunk_001"


def test_extract_fallback_terms():
    query = "what is the procedure for replacing the cooling fan in this machine"
    fallback = _extract_fallback_terms(query)
    assert "what" not in fallback.split()
    assert "is" not in fallback.split()
    assert "procedure" in fallback
    assert "cooling" in fallback
    assert "fan" in fallback


def test_retrieval_fallback_executes_when_hybrid_returns_empty():
    with patch(
        "app.services.core.retrieval_service.execute_hybrid_search",
        return_value=[],
    ), patch(
        "app.services.core.retrieval_service.search_chunks_by_keyword",
        return_value=[{"chunk_id": "fb_1", "file_hash": "h1", "page_number": 5, "text": "Fan replacement"}],
    ) as mock_fb, patch(
        "app.services.core.retrieval_service.rerank_chunks",
        side_effect=lambda query, candidates, top_k: candidates,
    ):
        res = retrieve_chunks("how do I replace the cooling fan")

    assert len(res) == 1
    assert res[0]["chunk_id"] == "fb_1"
    assert mock_fb.called
