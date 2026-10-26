import json
import logging
import re
from typing import Any

from google import genai

from app.config import (
    GEMINI_API_KEY,
    GEMINI_GENERATION_MODEL,
    RERANK_CANDIDATE_LIMIT,
    RERANKING_ENABLED,
    RETRIEVAL_TOP_K,
)

logger = logging.getLogger(__name__)

client = genai.Client(
    api_key=GEMINI_API_KEY
)


def build_rerank_prompt(query: str, candidates: list[dict[str, Any]]) -> str:
    """Build a prompt asking the model to rank candidate indices by relevance."""
    candidate_lines = []
    for idx, c in enumerate(candidates, start=1):
        snippet = (c.get("text") or "").strip()[:350]
        candidate_lines.append(f"[{idx}] {snippet}")
    candidates_text = "\n\n".join(candidate_lines)

    return (
        "You are an expert technical document reranker.\n"
        "Evaluate the following candidate passages based on how directly they answer the user's query.\n"
        "Rank the passages from most relevant to least relevant.\n\n"
        f"Query: {query.strip()}\n\n"
        "Candidates:\n"
        f"{candidates_text}\n\n"
        "Output ONLY a JSON array of candidate numbers ordered by relevance (e.g. [2, 1, 3]). "
        "Do not include any explanation or markdown formatting."
    )


def parse_ranked_indices(response_text: str, num_candidates: int) -> list[int]:
    """Parse JSON array of 1-based candidate indices with safe fallback."""
    if not response_text:
        return list(range(1, num_candidates + 1))

    match = re.search(r"\[([\d\s,]+)\]", response_text)
    if match:
        try:
            raw_indices = json.loads(f"[{match.group(1)}]")
            valid_indices: list[int] = []
            seen: set[int] = set()
            for idx in raw_indices:
                if isinstance(idx, int) and 1 <= idx <= num_candidates and idx not in seen:
                    valid_indices.append(idx)
                    seen.add(idx)

            if valid_indices:
                # Append any omitted candidate indices in original order
                for i in range(1, num_candidates + 1):
                    if i not in seen:
                        valid_indices.append(i)
                return valid_indices
        except Exception:
            pass

    return list(range(1, num_candidates + 1))


def rerank_chunks(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = RETRIEVAL_TOP_K,
    enabled: bool = RERANKING_ENABLED,
    candidate_limit: int = RERANK_CANDIDATE_LIMIT,
) -> list[dict[str, Any]]:
    """
    Rerank a bounded candidate list based on relevance to the query.

    - Bounded candidate pool (default top 10 from RRF).
    - Preserves all original chunk text and metadata.
    - If disabled, on single candidate, or on model error, cleanly falls back to RRF order.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if not candidates:
        return []

    # If reranking is disabled or unnecessary for 1 candidate, return top_k directly
    if not enabled or len(candidates) <= 1:
        return candidates[:top_k]

    pool = candidates[:candidate_limit]

    try:
        prompt = build_rerank_prompt(query, pool)
        response = client.models.generate_content(
            model=GEMINI_GENERATION_MODEL,
            contents=prompt,
        )

        ranked_order = parse_ranked_indices(
            response.text if response else "",
            len(pool),
        )

        reranked_pool = [pool[idx - 1] for idx in ranked_order]
        # Attach any candidates beyond the pool at the end
        full_results = reranked_pool + candidates[candidate_limit:]
        return full_results[:top_k]

    except Exception as exc:
        logger.warning(
            "Reranking model failed, falling back to RRF ranking: %s",
            exc.__class__.__name__,
        )
        return candidates[:top_k]
