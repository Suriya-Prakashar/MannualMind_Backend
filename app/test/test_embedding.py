from app.services.embedding_service import (
    generate_embedding,
    EMBEDDING_DIMENSION,
)


def main():

    sample_text = """
    The hydraulic filter should be replaced
    when contamination is detected.
    """

    embedding = generate_embedding(
        sample_text
    )

    print(
        "Embedding generated successfully"
    )

    print(
        "Embedding dimension:",
        len(embedding)
    )

    print(
        "Expected dimension:",
        EMBEDDING_DIMENSION
    )

    print(
        "First 5 values:",
        embedding[:5]
    )


if __name__ == "__main__":
    main()