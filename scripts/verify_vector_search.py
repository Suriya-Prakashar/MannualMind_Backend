from app.database import mongodb
from app.services.core.embedding_service import (
    generate_embedding,
)
from app.services.core.vector_search_service import (
    search_similar_chunks,
)


def main():
    mongodb.connect()

    try:
        query = "What Samsung laptop models are covered in this repair guide?"

        print("Query:", query)
        print("\nGenerating query embedding...")

        query_embedding = generate_embedding(query)

        print("Embedding dimensions:", len(query_embedding))

        print("\nSearching MongoDB Atlas...")

        results = search_similar_chunks(
            query_embedding=query_embedding,
            limit=5,
        )

        print("\nSearch results:")

        for rank, result in enumerate(results, start=1):
            print(
                f"\n{rank}. Chunk: {result['chunk_id']}"
            )
            print(f"   Page: {result['page_number']}")
            print(f"   Score: {result['score']}")
            print(f"   Text: {result['text'][:250]}")

        print("\nTotal results:", len(results))

        if not results:
            print(
                "\nNo results returned. Check the Atlas "
                "index and stored embeddings."
            )
        else:
            print("\nVECTOR SEARCH TEST PASSED")

    finally:
        mongodb.close()


if __name__ == "__main__":
    main()