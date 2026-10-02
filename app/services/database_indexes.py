from app.database import mongodb


def create_indexes():
    mongodb.collection.create_index(
        "file_hash",
        unique=True,
        name="unique_file_hash",
    )

    print("MongoDB indexes created successfully")