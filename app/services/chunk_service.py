from typing import List


DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


def create_page_chunks(
    text: str,
    file_hash: str,
    page_number: int,
    images: List[dict] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[dict]:
    """
    Split one PDF page into overlapping text chunks.

    Each chunk keeps:
    - file hash
    - page number
    - chunk index
    - chunk text
    - image metadata
    """

    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0"
        )

    if chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap cannot be negative"
        )

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    text = text.strip()

    if images is None:
        images = []

    chunks = []

    start = 0
    chunk_index = 1
    text_length = len(text)

    while start < text_length:

        end = start + chunk_size

        chunk_text = text[start:end].strip()

        if chunk_text:

            chunk_id = (
                f"{file_hash}"
                f"_page_{page_number}"
                f"_chunk_{chunk_index}"
            )

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "file_hash": file_hash,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "images": images,
                }
            )

        if end >= text_length:
            break

        start = end - chunk_overlap
        chunk_index += 1

    return chunks