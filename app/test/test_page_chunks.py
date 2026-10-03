from app.services.chunk_service import create_page_chunks


def main():

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

    print(f"Total chunks: {len(chunks)}")

    for chunk in chunks:

        print("\n--------------------")

        print(f"Chunk ID: {chunk['chunk_id']}")
        print(f"File Hash: {chunk['file_hash']}")
        print(f"Page: {chunk['page_number']}")
        print(f"Chunk Index: {chunk['chunk_index']}")

        print("\nText:")
        print(chunk["text"])

        print("\nImages:")

        for image in chunk["images"]:
            print(f"  Image ID: {image['image_id']}")
            print(f"  Filename: {image['filename']}")
            print(f"  Path: {image['path']}")


if __name__ == "__main__":
    main()