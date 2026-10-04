from app.services import file_hash
import pymupdf

from app.services.pdf_service import extract_text_and_images_from_pdf


def test_extract_text_and_images_from_pdf(tmp_path):
    pdf_path = tmp_path / "test_manual.pdf"

    document = pymupdf.open()

    page = document.new_page()
    page.insert_text((72, 72), "ManualMind PDF test page")

    image = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, 100, 100),
        0,
    )
    image.clear_with(255)

    image_path = tmp_path / "test_image.png"
    image.save(str(image_path))

    page.insert_image(
        pymupdf.Rect(100, 100, 200, 200),
        filename=str(image_path),
    )

    document.save(str(pdf_path))
    document.close()

    file_hash = "test_pdf_hash"

    pages = extract_text_and_images_from_pdf(
        str(pdf_path),
        file_hash,
    )

    assert len(pages) == 1

    page_data = pages[0]

    assert page_data["page_number"] == 1
    assert "ManualMind PDF test page" in page_data["text"]

    assert len(page_data["images"]) == 1

    image_data = page_data["images"][0]

    assert image_data["image_id"] == "page_1_image_1"
    assert image_data["filename"] == "page_1_image_1.png"
    assert image_data["path"]