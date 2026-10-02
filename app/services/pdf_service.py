from pathlib import Path
import json

import fitz


def extract_text_and_images_from_pdf(
    file_path: str,
    file_hash: str,
) -> list[dict]:

    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {file_path}"
        )

    # Hash-based extraction directory
    extraction_dir = (
        Path("data")
        / "extracted"
        / file_hash
    )

    image_dir = extraction_dir / "images"

    extraction_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    image_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    pages = []

    with fitz.open(pdf_path) as pdf:

        for page_number, page in enumerate(
            pdf,
            start=1,
        ):

            # Extract text
            text = page.get_text("text").strip()

            images = []

            image_list = page.get_images(
                full=True
            )

            for image_index, image_info in enumerate(
                image_list,
                start=1,
            ):

                xref = image_info[0]

                image_data = pdf.extract_image(
                    xref
                )

                image_bytes = image_data["image"]
                image_ext = image_data["ext"]

                image_filename = (
                    f"page_{page_number}"
                    f"_image_{image_index}"
                    f".{image_ext}"
                )

                image_path = (
                    image_dir / image_filename
                )

                # Don't overwrite existing image
                if not image_path.exists():
                    with image_path.open("wb") as image_file:
                        image_file.write(image_bytes)

                images.append(
                    {
                        "image_id": (
                            f"page_{page_number}"
                            f"_image_{image_index}"
                        ),
                        "filename": image_filename,
                        "path": str(image_path),
                    }
                )

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "images": images,
                }
            )

    # Save extracted page information
    pages_file = extraction_dir / "pages.json"

    if not pages_file.exists():
        with pages_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                pages,
                file,
                ensure_ascii=False,
                indent=2,
            )

    return pages