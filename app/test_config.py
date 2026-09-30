from app.config import (
    MONGODB_URI,
    MONGODB_DATABASE,
    MONGODB_COLLECTION,
)

print("MongoDB URI loaded:", bool(MONGODB_URI))
print("Database:", MONGODB_DATABASE)
print("Collection:", MONGODB_COLLECTION)