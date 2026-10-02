from app.database import mongodb


def find_by_file_hash(file_hash: str):
    return mongodb.collection.find_one(
        {
            "file_hash": file_hash
        }
    )


def create_document_record(
    filename: str,
    file_hash: str,
    total_pages: int,
    total_images: int,
):
    document = {
        "filename": filename,
        "file_hash": file_hash,
        "status": "processed",
        "total_pages": total_pages,
        "total_images": total_images,
    }

    result = mongodb.collection.insert_one(document)

    return str(result.inserted_id)