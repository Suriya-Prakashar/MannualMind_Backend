from app.services.chunk_embedding_service import (
    embed_chunks,
)
from app.services.chunk_repository import (
    create_chunk,
    find_chunk_by_id,
)
from app.services.chunk_service import (
    create_page_chunks,
)
from app.services.file_hash import (
    calculate_file_hash,
)
from app.services.pdf_service import (
    extract_text_and_images_from_pdf,
)


def ingest_pdf(
    pdf_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    max_pages: int | None = None,
) -> dict:
    """
    Process a PDF into embedded MongoDB chunks.

    Pipeline:

    PDF
    ↓
    SHA-256
    ↓
    Text + image extraction
    ↓
    Page chunks
    ↓
    Duplicate chunk check
    ↓
    Gemini embeddings
    ↓
    MongoDB storage

    Existing chunks are detected before generating
    embeddings to avoid unnecessary Gemini API calls.

    max_pages can be used to limit processing during
    testing and verification.
    """

    file_hash = calculate_file_hash(
        pdf_path
    )

    pages = extract_text_and_images_from_pdf(
        pdf_path,
        file_hash,
    )

    if max_pages is not None:
        pages = pages[:max_pages]

    total_pages = len(pages)

    total_chunks = 0
    new_chunks_count = 0
    inserted_chunks = 0
    skipped_chunks = 0

    for page in pages:

        page_chunks = create_page_chunks(
            text=page.get("text", ""),
            file_hash=file_hash,
            page_number=page["page_number"],
            images=page.get("images", []),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not page_chunks:
            continue

        total_chunks += len(page_chunks)

        chunks_to_embed = []

        for chunk in page_chunks:

            chunk_id = chunk["chunk_id"]

            existing_chunk = find_chunk_by_id(
                chunk_id
            )

            if existing_chunk:
                skipped_chunks += 1
                continue

            chunks_to_embed.append(
                chunk
            )

        if not chunks_to_embed:
            continue

        embedded_chunks = embed_chunks(
            chunks_to_embed
        )

        new_chunks_count += len(
            embedded_chunks
        )

        for chunk in embedded_chunks:

            create_chunk(chunk)

            inserted_chunks += 1

    return {
        "file_hash": file_hash,
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "new_chunks": new_chunks_count,
        "inserted_chunks": inserted_chunks,
        "skipped_chunks": skipped_chunks,
    }