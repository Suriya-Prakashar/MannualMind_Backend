from app.services.embedding_service import generate_embedding


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Generate embeddings for valid text chunks.

    The original chunk metadata is preserved and the generated
    embedding is added to each chunk.
    """

    embedded_chunks = []

    for chunk in chunks:

        text = chunk.get("text", "").strip()

        if not text:
            continue

        embedding = generate_embedding(text)

        embedded_chunk = {
            **chunk,
            "embedding": embedding,
        }

        embedded_chunks.append(
            embedded_chunk
        )

    return embedded_chunks