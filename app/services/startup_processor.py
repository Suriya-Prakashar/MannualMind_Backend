from pathlib import Path

from app.services.document_repository import (
    create_document_record,
    find_by_file_hash,
)
from app.services.file_hash import calculate_file_hash
from app.services.pdf_service import (
    extract_text_and_images_from_pdf,
)


MANUALS_DIR = Path("data/manuals")


def process_existing_pdfs() -> None:
    """
    Process PDF manuals found in data/manuals.

    A PDF is identified by its SHA-256 file hash.
    If the hash already exists in MongoDB, the PDF is skipped
    to prevent duplicate processing.
    """

    MANUALS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_files = sorted(
        MANUALS_DIR.glob("*.pdf")
    )

    if not pdf_files:
        print("No PDF manuals found.")
        return

    print(
        f"Found {len(pdf_files)} PDF manual(s)."
    )

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    for pdf_path in pdf_files:

        print(
            f"\nChecking: {pdf_path.name}"
        )

        try:
            # -------------------------------------------------
            # 1. Calculate SHA-256
            # -------------------------------------------------
            file_hash = calculate_file_hash(
                str(pdf_path)
            )

            print(
                f"SHA-256: {file_hash}"
            )

            # -------------------------------------------------
            # 2. Check duplicate
            # -------------------------------------------------
            existing_document = find_by_file_hash(
                file_hash
            )

            if existing_document:
                print(
                    f"Already processed. "
                    f"Skipping: {pdf_path.name}"
                )

                skipped_count += 1
                continue

            # -------------------------------------------------
            # 3. Extract text + images
            # -------------------------------------------------
            print(
                f"Extracting: {pdf_path.name}"
            )

            pages = extract_text_and_images_from_pdf(
                str(pdf_path),
                file_hash,
            )

            # -------------------------------------------------
            # 4. Calculate extraction statistics
            # -------------------------------------------------
            total_pages = len(pages)

            total_images = sum(
                len(page.get("images", []))
                for page in pages
            )

            # -------------------------------------------------
            # 5. Store document metadata
            # -------------------------------------------------
            create_document_record(
                filename=pdf_path.name,
                file_hash=file_hash,
                total_pages=total_pages,
                total_images=total_images,
            )

            processed_count += 1

            print(
                f"Processed successfully: "
                f"{pdf_path.name}"
            )

            print(
                f"Pages: {total_pages}"
            )

            print(
                f"Images: {total_images}"
            )

        except Exception as error:
            failed_count += 1

            print(
                f"Failed to process "
                f"{pdf_path.name}: {error}"
            )

    # ---------------------------------------------------------
    # Processing summary
    # ---------------------------------------------------------
    print("\n========================================")
    print("Startup PDF Processing Summary")
    print("========================================")
    print(f"Processed : {processed_count}")
    print(f"Skipped   : {skipped_count}")
    print(f"Failed    : {failed_count}")
    print("========================================")