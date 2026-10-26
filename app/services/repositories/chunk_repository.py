import re

from app.database import mongodb


def create_chunk(chunk: dict) -> str:
    """
    Insert one embedded chunk into MongoDB.
    """

    result = mongodb.chunks_collection.insert_one(
        chunk
    )

    return str(result.inserted_id)


def find_chunk_by_id(chunk_id: str):
    """
    Find a chunk using its unique chunk_id.
    """

    return mongodb.chunks_collection.find_one(
        {
            "chunk_id": chunk_id
        }
    )


def create_chunks(chunks: list[dict]) -> int:
    """
    Insert multiple embedded chunks into MongoDB.

    Returns the number of chunks inserted.
    """

    if not chunks:
        return 0

    result = mongodb.chunks_collection.insert_many(
        chunks
    )

    return len(result.inserted_ids)


def search_chunks_by_keyword(
    query: str,
    limit: int = 5,
) -> list[dict]:
    """
    Find chunks containing the user's query terms.
    This is basic keyword retrieval, not semantic search.
    """

    if not query or not query.strip():
        return []

    if limit < 1:
        raise ValueError("limit must be greater than 0")


    terms = query.strip().split()

    pattern = "|".join(
        re.escape(term) for term in terms
    )

    cursor = mongodb.chunks_collection.find(
        {
            "text": {
                "$regex": pattern,
                "$options": "i",
            }
        },
        {
            "_id": 0,
            "chunk_id": 1,
            "file_hash": 1,
            "page_number": 1,
            "text": 1,
            "images": 1,
        },
    ).limit(limit)

    return list(cursor)