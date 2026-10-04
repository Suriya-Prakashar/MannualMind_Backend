from app.services.chunk_service import create_page_chunks


def test_create_page_chunks():
    sample_text = """
    The hydraulic filter is located on the left
    side of the hydraulic assembly.

    Before removing the filter, switch off the
    machine and release hydraulic pressure.

    Remove the filter housing carefully and inspect
    the filter element for contamination or damage.

    Replace the filter if the element is damaged.
    """

    file_hash = "abc123testhash"
    page_number = 12

    images = [
        {
            "image_id": "page_12_image_1",
            "filename": "page_12_image_1.png",
            "path": (
                "data/extracted/"
                "abc123testhash/images/"
                "page_12_image_1.png"
            ),
        }
    ]

    chunks = create_page_chunks(
        text=sample_text,
        file_hash=file_hash,
        page_number=page_number,
        images=images,
        chunk_size=200,
        chunk_overlap=50,
    )

    assert len(chunks) > 0

    for index, chunk in enumerate(chunks, start=1):
        assert chunk["chunk_id"] == (
            f"{file_hash}_page_{page_number}_chunk_{index}"
        )
        assert chunk["file_hash"] == file_hash
        assert chunk["page_number"] == page_number
        assert chunk["chunk_index"] == index
        assert chunk["text"]
        assert chunk["images"] == images