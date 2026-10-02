from app.services.pdf_service import extract_text_and_images_from_pdf


PDF_PATH = "data/technical_manual.pdf"


def main():
    pages = extract_text_and_images_from_pdf(PDF_PATH)

    print(f"Total pages: {len(pages)}")

    total_images = 0

    for page in pages[:10]:
        print("\n--------------------")
        print(f"Page: {page['page_number']}")

        print("\nText:")
        print(page["text"][:300])

        print("\nImages:")

        for image in page["images"]:
            print(f"  Image ID: {image['image_id']}")
            print(f"  Filename: {image['filename']}")
            print(f"  Path: {image['path']}")

        total_images += len(page["images"])

    print("\n====================")
    print(f"Images in first 3 pages: {total_images}")


if __name__ == "__main__":
    main()