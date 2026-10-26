from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.database import mongodb
from app.services.core.startup_processor import (
    process_existing_pdfs,
)
from app.services.utils.database_indexes import create_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting ManualMind Backend...")
    mongodb.connect()
    create_indexes()
    process_existing_pdfs()
    print("ManualMind Backend started successfully")
    yield
    mongodb.close()
    print("ManualMind Backend stopped")


app = FastAPI(
    title="ManualMind Backend",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mongodb": "connected",
    }


@app.get("/")
async def root():
    return {
        "message": "ManualMind Backend is running"
    }


app.include_router(documents_router)
app.include_router(query_router)

# Mount extracted PDF images directory for static retrieval
extracted_images_dir = Path("data") / "extracted"
extracted_images_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/images",
    StaticFiles(directory=str(extracted_images_dir)),
    name="static_images",
)