import glob
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def resolve_chunk_images(
    chunk: dict[str, Any],
    base_static_url: str = "/static/images",
) -> list[dict[str, Any]]:
    """
    Resolve and enrich image metadata for a retrieved manual chunk.

    1. Checks if images are already present in the chunk document.
    2. Fallback: inspects the extracted image directory on disk for the chunk's page.
    3. Adds public static HTTP URL (/static/images/<file_hash>/images/<filename>)
       to each image so frontend clients can display step diagrams.
    """
    file_hash = chunk.get("file_hash", "")
    page_number = chunk.get("page_number")

    images = list(chunk.get("images") or [])

    # If chunk metadata does not contain images, check disk extraction directory
    if not images and file_hash and page_number:
        image_dir = Path("data") / "extracted" / file_hash / "images"
        if image_dir.exists():
            pattern = str(image_dir / f"page_{page_number}_image_*.*")
            matching_files = glob.glob(pattern)
            for idx, img_path_str in enumerate(matching_files, start=1):
                p = Path(img_path_str)
                images.append(
                    {
                        "image_id": f"page_{page_number}_image_{idx}",
                        "filename": p.name,
                        "path": str(p),
                    }
                )

    enriched_images = []
    for img in images:
        filename = img.get("filename")
        if not filename and img.get("path"):
            filename = Path(img["path"]).name

        url = f"{base_static_url}/{file_hash}/images/{filename}" if (file_hash and filename) else None

        enriched_images.append(
            {
                "image_id": img.get("image_id", f"page_{page_number}_image"),
                "filename": filename,
                "page_number": page_number,
                "url": url,
                "path": img.get("path"),
            }
        )

    return enriched_images


def collect_unique_images_from_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract a deduplicated list of images across all retrieved chunks.
    """
    seen_ids = set()
    unique_images = []

    for chunk in chunks:
        chunk_images = resolve_chunk_images(chunk)
        for img in chunk_images:
            identifier = img.get("url") or img.get("image_id") or img.get("filename")
            if identifier and identifier not in seen_ids:
                seen_ids.add(identifier)
                unique_images.append(img)

    return unique_images
