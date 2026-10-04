import uuid

from app.database import mongodb


def test_document_crud():
    mongodb.connect()

    test_file_hash = f"test_hash_{uuid.uuid4().hex}"

    test_document = {
        "type": "test",
        "project": "ManualMind",
        "message": "MongoDB CRUD test",
        "file_hash": test_file_hash,
    }

    document_id = None

    try:
        document_id = mongodb.insert_document(test_document)

        assert document_id is not None

        document = mongodb.find_document(document_id)

        assert document is not None
        assert document["type"] == "test"
        assert document["project"] == "ManualMind"
        assert document["message"] == "MongoDB CRUD test"
        assert document["file_hash"] == test_file_hash

    finally:
        if document_id is not None:
            mongodb.collection.delete_one({"_id": document_id})

        mongodb.close()