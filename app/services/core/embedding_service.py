from google import genai

from app.config import GEMINI_API_KEY


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768


client = genai.Client(
    api_key=GEMINI_API_KEY
)


def generate_embedding(text: str) -> list[float]:
    """
    Generate a 768-dimensional embedding for the given text.
    """

    if not text or not text.strip():
        raise ValueError(
            "Text cannot be empty"
        )

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text.strip(),
        config={
            "output_dimensionality": EMBEDDING_DIMENSION,
        },
    )

    embedding = response.embeddings[0].values

    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Unexpected embedding dimension: "
            f"{len(embedding)}"
        )

    return embedding