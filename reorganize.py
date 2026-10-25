import os
import glob
from pathlib import Path

base_dir = Path("c:/Users/acer/OneDrive/Documents/ManualMind/ManualMind-backend")
services_dir = base_dir / "app" / "services"

# Create directories
(services_dir / "repositories").mkdir(exist_ok=True)
(services_dir / "core").mkdir(exist_ok=True)
(services_dir / "utils").mkdir(exist_ok=True)

# Create __init__.py
(services_dir / "repositories" / "__init__.py").touch()
(services_dir / "core" / "__init__.py").touch()
(services_dir / "utils" / "__init__.py").touch()

# Mapping of file to its new subfolder
file_mapping = {
    "chunk_repository.py": "repositories",
    "document_repository.py": "repositories",
    "chunk_embedding_service.py": "core",
    "chunk_service.py": "core",
    "embedding_service.py": "core",
    "ingestion_service.py": "core",
    "pdf_service.py": "core",
    "startup_processor.py": "core",
    "database_indexes.py": "utils",
    "file_hash.py": "utils"
}

# Move files
for file_name, subfolder in file_mapping.items():
    src = services_dir / file_name
    dest = services_dir / subfolder / file_name
    if src.exists():
        src.rename(dest)
        print(f"Moved {file_name} to {subfolder}")

# Mapping for import replacements
import_replacements = {
    "app.services.repositories.chunk_repository": "app.services.repositories.chunk_repository",
    "app.services.repositories.document_repository": "app.services.repositories.document_repository",
    "app.services.core.chunk_embedding_service": "app.services.core.chunk_embedding_service",
    "app.services.core.chunk_service": "app.services.core.chunk_service",
    "app.services.core.embedding_service": "app.services.core.embedding_service",
    "app.services.core.ingestion_service": "app.services.core.ingestion_service",
    "app.services.core.pdf_service": "app.services.core.pdf_service",
    "app.services.core.startup_processor": "app.services.core.startup_processor",
    "app.services.utils.database_indexes": "app.services.utils.database_indexes",
    "app.services.utils.file_hash": "app.services.utils.file_hash",
    "from app.services.core import chunk_embedding_service": "from app.services.core import chunk_embedding_service",
    "from app.services.core import ingestion_service": "from app.services.core import ingestion_service",
    "from app.services.utils import file_hash": "from app.services.utils import file_hash",
}

# Find all python files to update
python_files = glob.glob(str(base_dir / "**/*.py"), recursive=True)

for py_file in python_files:
    if "venv" in py_file or ".pytest_cache" in py_file:
        continue
    
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old_import, new_import in import_replacements.items():
        new_content = new_content.replace(old_import, new_import)
        
    if new_content != content:
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated imports in {py_file}")

print("Done reorganizing and updating imports.")
