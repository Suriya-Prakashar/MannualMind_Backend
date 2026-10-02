import hashlib
from pathlib import Path


def calculate_file_hash(
    file_path: str,
    chunk_size: int = 1024 * 1024,
) -> str:
    """
    Calculate SHA-256 hash of a file.

    Reads the file in chunks so large PDF files
    do not need to be loaded entirely into memory.
    """

    sha256 = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        while chunk := file.read(chunk_size):
            sha256.update(chunk)

    return sha256.hexdigest()