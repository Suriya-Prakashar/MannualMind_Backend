
from pathlib import Path
import hashlib

from app.database import mongodb

pdf_path = Path("data/manuals/technical_manual.pdf")

if not pdf_path.exists():
    raise FileNotFoundError(f"PDF not found: {pdf_path}")

file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

print("PDF:", pdf_path)
print("SHA-256:", file_hash)

mongodb.connect()

try:
    collection = mongodb.chunks_collection

    count = collection.count_documents({"file_hash": file_hash})
    print("Existing chunks for this PDF:", count)

    sample = collection.find_one(
        {"file_hash": file_hash},
        {"_id": 0, "chunk_id": 1, "page_number": 1, "text": 1},
    )

    if sample:
        print("Sample chunk ID:", sample["chunk_id"])
        print("Sample page:", sample["page_number"])
        print("Sample text:", sample["text"][:200])
    else:
        print("This PDF hash was not found in the chunks collection.")

finally:
    mongodb.close()
