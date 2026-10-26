import json
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.core.query_service import process_query, process_query_stream

router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Question about a technical manual",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for multi-turn conversation tracking",
    )


class ImageItem(BaseModel):
    image_id: Optional[str] = None
    filename: Optional[str] = None
    page_number: Optional[int] = None
    url: Optional[str] = None
    path: Optional[str] = None


class SourceItem(BaseModel):
    page_number: int
    chunk_id: str
    snippet: str
    images: Optional[list[ImageItem]] = None


class QueryResponse(BaseModel):
    query: str
    route: str = "RAG"
    primary_route: Optional[str] = None
    intent: Optional[str] = None
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    images: Optional[list[ImageItem]] = None
    status: str
    message: str
    session_id: Optional[str] = None
    clarification_question: Optional[str] = None
    missing_information: Optional[list[str]] = None
    execution_steps: Optional[list[dict[str, Any]]] = None
    requires_approval: Optional[bool] = None
    tool_result: Optional[dict[str, Any]] = None


@router.post("/", response_model=QueryResponse, response_model_exclude_none=True)
async def query_document(request: QueryRequest):
    try:
        if request.session_id:
            return process_query(request.query, session_id=request.session_id)
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


@router.post("/stream")
async def stream_query_document(request: QueryRequest):
    """
    Stream answer tokens and multimodal metadata in Server-Sent Events (SSE) format.
    Clients receive:
      - event: metadata (sources, images, route)
      - event: token (incremental words/tokens)
      - event: done (final aggregated answer)
    """
    def event_generator():
        try:
            for event in process_query_stream(request.query, session_id=request.session_id):
                event_name = event.get("event", "message")
                data_str = json.dumps(event.get("data", {}))
                yield f"event: {event_name}\ndata: {data_str}\n\n"
        except ValueError as exc:
            err = json.dumps({"error": str(exc), "status": 400})
            yield f"event: error\ndata: {err}\n\n"
        except Exception as exc:
            err = json.dumps({"error": str(exc), "status": 500})
            yield f"event: error\ndata: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )