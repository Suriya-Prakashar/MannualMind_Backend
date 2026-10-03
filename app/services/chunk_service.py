from typing import List


def create_page_chunks(
    text: str,
    file_hash: str,
    page_number: int,
    images: List[dict] | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[dict]:

    if not text or not text.strip():
        return []

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