import pytest

from app.services.embedding_service import (
    EMBEDDING_DIMENSION,
    generate_embedding,
)


def test_generate_embedding_rejects_empty_text():
    with pytest.raises(ValueError, match="Text cannot be empty"):
        generate_embedding("")


def test_embedding_dimension_constant():
    assert EMBEDDING_DIMENSION == 768