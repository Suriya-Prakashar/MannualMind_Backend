from unittest.mock import MagicMock, patch

from app.database import mongodb


def test_mongodb_connection():
    """Test that MongoDB client initializes database and collections properly."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_db.name = "manualmind"
    mock_collection = MagicMock()
    mock_collection.name = "documents"
    mock_chunks = MagicMock()
    mock_chunks.name = "chunks"

    def get_collection(name):
        return mock_chunks if name == "chunks" else mock_collection

    mock_db.__getitem__.side_effect = get_collection
    mock_client.__getitem__.return_value = mock_db

    with patch("app.database.MongoClient", return_value=mock_client):
        mongodb.connect()

        assert mongodb.database is not None
        assert mongodb.collection is not None
        assert mongodb.chunks_collection is not None
        assert mongodb.database.name == "manualmind"
        assert mongodb.collection.name == "documents"

        mock_client.admin.command.assert_called_once_with("ping")

        mongodb.close()
        assert mongodb.client is None