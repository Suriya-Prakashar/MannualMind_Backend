from fastapi import FastAPI
from app.database import mongodb


app = FastAPI(
    title="ManualMind Backend",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    mongodb.connect()


@app.on_event("shutdown")
def shutdown():
    mongodb.close()


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "mongodb": "connected",
    }