from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pymongo.errors import DuplicateKeyError

from app.services.repositories.document_repository import (
    create_document_record,
    find_by_file_hash,
)
from app.services.utils.file_hash import calculate_file_hash
from app.services.core.ingestion_service import ingest_pdf


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

UPLOAD_DIR = Path("data/manuals")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):

    # 1. Validate PDF
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    # 2. Save PDF
    file_path = UPLOAD_DIR / file.filename

    try:
        with file_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)

        # 3. Calculate SHA-256
        file_hash = calculate_file_hash(str(file_path))

        # 4. Check if already processed
        existing_document = find_by_file_hash(file_hash)

        if existing_document:
            # Clean up the duplicate file that was just uploaded
            file_path.unlink(missing_ok=True)
            return {
                "message": "PDF already processed",
                "filename": existing_document["filename"],
                "file_hash": file_hash,
                "status": "skipped",
                "document_id": str(existing_document["_id"]),
            }

        # 5. Extract text + images and chunk/embed via ingest_pdf
        try:
            result = ingest_pdf(str(file_path))
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            )
        except Exception as error:
            raise Exception(f"PDF extraction and ingestion failed: {error}")

        # 6. Store document record
        try:
            document_id = create_document_record(
                filename=file.filename,
                file_hash=file_hash,
                total_pages=result["total_pages"],
                total_images=0,
            )
        except DuplicateKeyError:
            existing_document = find_by_file_hash(file_hash)
            return {
                "message": "PDF already processed",
                "filename": existing_document["filename"],
                "file_hash": file_hash,
                "status": "skipped",
                "document_id": str(existing_document["_id"]),
            }

        return {
            "message": "PDF uploaded and processed successfully",
            "filename": file.filename,
            "file_hash": file_hash,
            "status": "processed",
            "document_id": document_id,
            "total_pages": result["total_pages"],
            "total_chunks": result["total_chunks"],
            "inserted_chunks": result["inserted_chunks"]
        }

    except Exception as e:
        # Cleanup the file if anything failed
        if file_path.exists():
            file_path.unlink(missing_ok=True)

        if isinstance(e, HTTPException):
            raise e

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )