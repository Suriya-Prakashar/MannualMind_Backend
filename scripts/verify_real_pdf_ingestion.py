from pathlib import Path

from app.database import mongodb
from app.services.ingestion_service import ingest_pdf


MANUALS_DIR = Path("data/manuals")


def main():
    pdf_files = sorted(
        MANUALS_DIR.glob("*.pdf")
    )

    if not pdf_files:
        raise FileNotFoundError(
            "No PDF files found in data/manuals"
        )

    pdf_path = pdf_files[0]

    print("========================================")
    print("REAL PDF INGESTION TEST")
    print("========================================")
    print(f"PDF: {pdf_path.name}")
    print("Maximum pages: 3")
    print()

    mongodb.connect()

    try:
        result = ingest_pdf(
            pdf_path=str(pdf_path),
            max_pages=3,
        )

        print()
        print("========================================")
        print("INGESTION RESULT")
        print("========================================")

        print(
            f"File hash       : "
            f"{result['file_hash']}"
        )

        print(
            f"Pages processed : "
            f"{result['total_pages']}"
        )

        print(
            f"Total chunks    : "
            f"{result['total_chunks']}"
        )

        print(
            f"Inserted chunks : "
            f"{result['inserted_chunks']}"
        )

        print(
            f"Skipped chunks  : "
            f"{result['skipped_chunks']}"
        )

        print()

        stored_count = mongodb.chunks_collection.count_documents(
            {
                "file_hash": result["file_hash"]
            }
        )

        print(
            f"MongoDB chunks  : "
            f"{stored_count}"
        )

        if stored_count == 0:
            raise RuntimeError(
                "No chunks were stored in MongoDB."
            )

        sample_chunk = (
            mongodb.chunks_collection.find_one(
                {
                    "file_hash": result["file_hash"]
                }
            )
        )

        if sample_chunk is None:
            raise RuntimeError(
                "Could not retrieve stored chunk."
            )

        print()
        print("Sample stored chunk:")
        print(
            f"chunk_id       : "
            f"{sample_chunk['chunk_id']}"
        )

        print(
            f"page_number    : "
            f"{sample_chunk['page_number']}"
        )

        print(
            f"text_length    : "
            f"{len(sample_chunk['text'])}"
        )

        print(
            f"embedding_dim  : "
            f"{len(sample_chunk['embedding'])}"
        )

        if len(sample_chunk["embedding"]) != 768:
            raise RuntimeError(
                "Embedding dimension is not 768."
            )

        print()
        print("REAL PDF INGESTION TEST PASSED")

    finally:
        mongodb.close()


if __name__ == "__main__":
    main()