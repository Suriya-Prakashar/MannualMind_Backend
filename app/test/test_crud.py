from app.database import mongodb


def main():
    mongodb.connect()

    test_document = {
        "type": "test",
        "project": "ManualMind",
        "message": "MongoDB CRUD test"
    }

    document_id = mongodb.insert_document(test_document)

    print("Inserted ID:", document_id)

    document = mongodb.find_document(document_id)

    print("Retrieved document:")
    print(document)

    mongodb.close()


if __name__ == "__main__":
    main()