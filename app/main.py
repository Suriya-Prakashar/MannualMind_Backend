from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.database import mongodb
from app.services.database_indexes import create_indexes
from app.services.startup_processor import (
    process_existing_pdfs,
)


app = FastAPI(
    title="ManualMind Backend",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    print("Starting ManualMind Backend...")
    mongodb.connect()
    create_indexes()
    process_existing_pdfs()
    print("ManualMind Backend started successfully")


@app.on_event("shutdown")
def shutdown():
    mongodb.close()
    print("ManualMind Backend stopped")


@app.get("/health")
def health_check():

    return {
        "status": "healthy",
        "mongodb": "connected",
    }


app.include_router(
    documents_router
)