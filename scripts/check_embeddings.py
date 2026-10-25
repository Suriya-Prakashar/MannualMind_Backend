
from app.database import mongodb
from app.services.core.vector_search_service import search_similar_chunks

mongodb.connect()

try:
    collection = mongodb.chunks_collection

    sample = collection.find_one(
        {"embedding": {"$exists": True}},
        {"_id": 0, "chunk_id": 1, "embedding": 1},
    )

    if not sample:
        print("ERROR: No embedded chunks found.")
    else:
        print("Testing chunk:", sample["chunk_id"])
        print("Embedding dimensions:", len(sample["embedding"]))

        results = search_similar_chunks(
            query_embedding=sample["embedding"],
            limit=5,
        )

        print("Results returned:", len(results))

        for result in results:
            print(
                "Chunk:", result["chunk_id"],
                "| Score:", result.get("score"),
            )

finally:
    mongodb.close()
