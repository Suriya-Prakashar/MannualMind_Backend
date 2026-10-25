import sys

from app.database import mongodb
from app.services.core.query_service import process_query


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What Samsung laptop models are covered in this repair guide?"
    )


    print(f"Connecting to MongoDB Atlas...")
    mongodb.connect()

    try:
        print(f"Query: {query}\n")
        print("Executing full RAG pipeline (Retrieval + Gemini Generation)...")
        result = process_query(query)

        print("\n" + "=" * 50)
        print("GENERATED ANSWER:")
        print("=" * 50)
        print(result["answer"])
        print("\n" + "=" * 50)
        print("SOURCES:")
        print("=" * 50)
        for i, source in enumerate(result.get("sources", []), start=1):
            print(f"[{i}] Chunk ID: {source['chunk_id']} | Page: {source['page_number']}")
            print(f"    Snippet: {source['snippet'][:200]}...\n")

        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")

    finally:
        mongodb.close()


if __name__ == "__main__":
    main()
