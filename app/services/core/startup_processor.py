from pathlib import Path

from app.services.repositories.document_repository import (
    find_by_file_hash,
    create_document_record,
)
from app.services.utils.file_hash import calculate_file_hash
from app.services.core.ingestion_service import ingest_pdf


MANUALS_DIR = Path("data/manuals")


def process_existing_pdfs() -> None:
    MANUALS_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(MANUALS_DIR.glob("*.pdf"))

    if not pdf_files:
        print("No PDF manuals found.")
        return

    print(f"Found {len(pdf_files)} PDF manual(s).")

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    for pdf_path in pdf_files:
        print(f"\nChecking: {pdf_path.name}")

        try:
            file_hash = calculate_file_hash(str(pdf_path))

            print(f"SHA-256: {file_hash}")

            existing_document = find_by_file_hash(file_hash)

            if existing_document:
                print(
                    f"Already processed. "
                    f"Skipping: {pdf_path.name}"
                )
                skipped_count += 1
                continue

            print(
                f"New manual detected. "
                f"Starting full ingestion: {pdf_path.name}"
            )

            result = ingest_pdf(
                pdf_path=str(pdf_path)
            )

            create_document_record(
                filename=pdf_path.name,
                file_hash=file_hash,
                total_pages=result["total_pages"],
                total_images=0,
            )

            processed_count += 1

            print(
                f"Processed successfully: "
                f"{pdf_path.name}"
            )

            print(
                f"Pages: {result['total_pages']}"
            )

            print(
                f"Chunks: {result['total_chunks']}"
            )

            print(
                f"New chunks: {result['new_chunks']}"
            )

            print(
                f"Inserted chunks: "
                f"{result['inserted_chunks']}"
            )

            print(
                f"Skipped chunks: "
                f"{result['skipped_chunks']}"
            )

        except Exception as error:
            failed_count += 1

            print(
                f"Failed to process "
                f"{pdf_path.name}: {error}"
            )

    print("\n========================================")
    print("Startup PDF Processing Summary")
    print("========================================")
    print(f"Processed : {processed_count}")
    print(f"Skipped   : {skipped_count}")
    print(f"Failed    : {failed_count}")
    print("========================================")