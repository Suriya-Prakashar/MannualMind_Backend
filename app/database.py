from pymongo import MongoClient

from app.config import (
    MONGODB_URI,
    MONGODB_DATABASE,
    MONGODB_COLLECTION,
)


class MongoDB:
    def __init__(self):
        self.client = None
        self.database = None
        self.collection = None
        self.chunks_collection = None

    def connect(self):
        self.client = MongoClient(MONGODB_URI)

        self.database = self.client[
            MONGODB_DATABASE
        ]

        # Existing documents collection
        self.collection = self.database[
            MONGODB_COLLECTION
        ]

        # New chunks collection
        self.chunks_collection = self.database[
            "chunks"
        ]

        # Verify connection
        self.client.admin.command("ping")

        print("MongoDB connected successfully")

    def close(self):
        if self.client:
            self.client.close()

            self.client = None
            self.database = None
            self.collection = None
            self.chunks_collection = None

            print("MongoDB connection closed")

    def insert_document(self, document: dict):
        result = self.collection.insert_one(
            document
        )

        return result.inserted_id

    def find_document(self, document_id):
        from bson import ObjectId

        return self.collection.find_one(
            {
                "_id": ObjectId(document_id)
            }
        )


mongodb = MongoDB()