from app.database import mongodb


VECTOR_INDEX_NAME = "vector_index"
VECTOR_PATH = "embedding"


def search_similar_chunks(
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    """Retrieve semantically similar chunks from MongoDB Atlas."""

    if len(query_embedding) != 768:
        raise ValueError(
            "Query embedding must contain 768 dimensions."
        )

    if limit < 1:
        raise ValueError("limit must be greater than 0.")

    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": VECTOR_PATH,
                "queryVector": query_embedding,
                "numCandidates": max(limit * 10, 50),
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "chunk_id": 1,
                "file_hash": 1,
                "page_number": 1,
                "text": 1,
                "images": 1,
                "score": {
                    "$meta": "vectorSearchScore"
                },
            }
        },
    ]

    return list(
        mongodb.chunks_collection.aggregate(pipeline)
    )