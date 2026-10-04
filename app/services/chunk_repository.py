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