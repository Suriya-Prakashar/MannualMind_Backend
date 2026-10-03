from google import genai

from app.config import GEMINI_API_KEY


client = genai.Client(
    api_key=GEMINI_API_KEY
)


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768


def generate_embedding(text: str) -> list[float]:

    if not text or not text.strip():
        raise ValueError(
            "Text cannot be empty"
        )

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "output_dimensionality": EMBEDDING_DIMENSION,
        },
    )

    return response.embeddings[0].values