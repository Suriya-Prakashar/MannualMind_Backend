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


def process_existing_pdfs():
    MANUALS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_files = list(
        MANUALS_DIR.glob("*.pdf")
    )

    if not pdf_files:
        print("No PDF manuals found.")
        return

    print(
        f"Found {len(pdf_files)} PDF manual(s)."
    )

    for pdf_path in pdf_files:

        print(
            f"Checking: {pdf_path.name}"
        )

        try:
            file_hash = calculate_file_hash(
                str(pdf_path)
            )

            existing_document = find_by_file_hash(
                file_hash
            )

            if existing_document:
                print(
                    f"Already processed: "
                    f"{pdf_path.name}"
                )
                continue

            print(
                f"Processing: "
                f"{pdf_path.name}"
            )

            pages = extract_text_and_images_from_pdf(
                str(pdf_path),
                file_hash,
            )

            total_images = sum(
                len(page["images"])
                for page in pages
            )

            create_document_record(
                filename=pdf_path.name,
                file_hash=file_hash,
                total_pages=len(pages),
                total_images=total_images,
            )

            print(
                f"Processed successfully: "
                f"{pdf_path.name}"
            )

        except Exception as error:
            print(
                f"Failed to process "
                f"{pdf_path.name}: {error}"
            )