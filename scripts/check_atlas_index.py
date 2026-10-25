
from app.database import mongodb

mongodb.connect()

try:
    collection = mongodb.chunks_collection

    print("Database:", collection.database.name)
    print("Collection:", collection.name)
    print("\nAtlas Search indexes:")

    indexes = list(collection.list_search_indexes())

    if not indexes:
        print("No search indexes found.")

    for index in indexes:
        print("\nIndex name:", index.get("name"))
        print("Type:", index.get("type"))
        print("Status:", index.get("status"))
        print("Queryable:", index.get("queryable"))
        print("Definition:", index.get("latestDefinition"))

finally:
    mongodb.close()
