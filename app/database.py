from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

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

    def connect(self):
        try:
            self.client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
            )

            # Verify MongoDB connection
            self.client.admin.command("ping")

            self.database = self.client[MONGODB_DATABASE]
            self.collection = self.database[MONGODB_COLLECTION]

            print("MongoDB connected successfully")

        except ConnectionFailure as error:
            print(f"MongoDB connection failed: {error}")
            raise
    
    def insert_document(self, document):
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    def find_document(self, document_id):
        from bson import ObjectId

        return self.collection.find_one(
            {"_id": ObjectId(document_id)}
        )

    def close(self):
        if self.client:
            self.client.close()
            print("MongoDB connection closed")


mongodb = MongoDB()