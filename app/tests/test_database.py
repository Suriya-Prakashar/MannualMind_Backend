from app.database import mongodb


def test_mongodb_connection():
    mongodb.connect()

    assert mongodb.database is not None
    assert mongodb.collection is not None
    assert mongodb.database.name
    assert mongodb.collection.name

    mongodb.close()