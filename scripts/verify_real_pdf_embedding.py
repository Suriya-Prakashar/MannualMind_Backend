from pathlib import Path

import pymupdf

from app.services.file_hash import calculate_file_hash
from app.services.chunk_service import create_page_chunks
from app.services.chunk_embedding_service import embed_chunks


# Number of pages to test
TEST_PAGES = 3


def extract_test_pages(pdf_path: Path, file_hash: str) -> list[dict]:
    """
    Extract only the first TEST_PAGES from the real PDF.

    This is used only for verification.
    It does not save or modify extracted files.
    """

    pages = []

    document = pymupdf.open(pdf_path)

    total_pages = len(document)
    pages_to_test = min(TEST_PAGES, total_pages)

    for page_index in range(pages_to_test):
        page = document[page_index]

        text = page.get_text("text").strip()

        images = []

        for image_index, image in enumerate(
            page.get_images(full=True),
            start=1,
        ):
            images.append(
                {
                    "image_id": f"page_{page_index + 1}_image_{image_index}"
                }
            )

        pages.append(
            {
                "page_number": page_index + 1,
                "text": text,
                "images": images,
            }
        )

    document.close()

    return pages


def main():
    print("=" * 60)
    print("ManualMind - Real PDF Embedding Verification")
    print("=" * 60)

    # --------------------------------------------------
    # 1. Find PDF
    # --------------------------------------------------

    manuals_dir = Path("data/manuals")

    pdf_files = list(manuals_dir.glob("*.pdf"))

    if not pdf_files:
        print("\nERROR: No PDF found in data/manuals/")
        return

    if len(pdf_files) > 1:
        print("\nMultiple PDFs found:")
        for pdf in pdf_files:
            print(f" - {pdf.name}")

        print("\nUsing the first PDF for this test.")

    pdf_path = pdf_files[0]

    print(f"\nPDF: {pdf_path.name}")
    print(f"Testing first {TEST_PAGES} pages")

    # --------------------------------------------------
    # 2. Calculate SHA-256
    # --------------------------------------------------

    file_hash = calculate_file_hash(str(pdf_path))

    print(f"\nFile hash: {file_hash}")

    # --------------------------------------------------
    # 3. Extract limited pages
    # --------------------------------------------------

    print("\nExtracting test pages...")

    pages = extract_test_pages(
        pdf_path=pdf_path,
        file_hash=file_hash,
    )

    print(f"Pages extracted for test: {len(pages)}")

    # --------------------------------------------------
    # 4. Create chunks
    # --------------------------------------------------

    all_chunks = []

    for page in pages:

        print(
            f"\nPage {page['page_number']}: "
            f"{len(page['text'])} characters, "
            f"{len(page['images'])} images"
        )

        page_chunks = create_page_chunks(
            text=page["text"],
            file_hash=file_hash,
            page_number=page["page_number"],
            images=page["images"],
        )

        all_chunks.extend(page_chunks)

        print(f"Chunks created: {len(page_chunks)}")

    print("\n" + "-" * 60)
    print(f"Total chunks from {len(pages)} pages: {len(all_chunks)}")
    print("-" * 60)

    if not all_chunks:
        print("\nERROR: No chunks were created.")
        return

    # --------------------------------------------------
    # 5. Generate embeddings
    # --------------------------------------------------

    print("\nGenerating Gemini embeddings...")

    embedded_chunks = embed_chunks(all_chunks)

    # --------------------------------------------------
    # 6. Verify embeddings
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("Embedding Verification")
    print("=" * 60)

    print(f"Pages tested: {len(pages)}")
    print(f"Chunks created: {len(all_chunks)}")
    print(f"Chunks embedded: {len(embedded_chunks)}")

    if len(embedded_chunks) != len(all_chunks):
        print("\nWARNING: Some chunks were not embedded.")

    for index, chunk in enumerate(embedded_chunks, start=1):

        embedding = chunk["embedding"]

        print("\n" + "-" * 60)
        print(f"Chunk {index}")
        print(f"Chunk ID: {chunk['chunk_id']}")
        print(f"Page: {chunk['page_number']}")
        print(f"Text length: {len(chunk['text'])}")
        print(f"Images referenced: {len(chunk.get('images', []))}")
        print(f"Embedding dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")

        if len(embedding) != 768:
            print("WARNING: Expected embedding dimension is 768.")

    # --------------------------------------------------
    # 7. Final result
    # --------------------------------------------------

    all_dimensions_correct = all(
        len(chunk["embedding"]) == 768
        for chunk in embedded_chunks
    )

    print("\n" + "=" * 60)

    if (
        len(embedded_chunks) == len(all_chunks)
        and all_dimensions_correct
    ):
        print("REAL PDF EMBEDDING TEST PASSED")
    else:
        print("REAL PDF EMBEDDING TEST FAILED")

    print("=" * 60)


if __name__ == "__main__":
    main()