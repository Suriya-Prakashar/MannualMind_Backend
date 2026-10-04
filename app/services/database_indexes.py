from app.database import mongodb


def create_indexes():
    # Prevent duplicate PDF documents
    mongodb.collection.create_index(
        "file_hash",
        unique=True,
        name="unique_file_hash",
    )

    # Prevent duplicate chunks
    mongodb.chunks_collection.create_index(
        "chunk_id",
        unique=True,
        name="unique_chunk_id",
    )

    print("MongoDB indexes created successfully")