from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.core.query_service import process_query

router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Question about a technical manual",
    )


class SourceItem(BaseModel):
    page_number: int
    chunk_id: str
    snippet: str


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[SourceItem]
    status: str
    message: str


@router.post("/", response_model=QueryResponse)
async def query_document(request: QueryRequest):
    try:
        return process_query(request.query)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc