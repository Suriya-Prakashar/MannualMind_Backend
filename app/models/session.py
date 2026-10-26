from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.routing import QueryIntent, RouteType


class ConversationTurn(BaseModel):
    user_query: str
    assistant_response: Optional[str] = None
    route: RouteType
    intent: Optional[QueryIntent] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingClarification(BaseModel):
    missing_fields: list[str] = Field(default_factory=list)
    original_query: str
    intent: QueryIntent = QueryIntent.TROUBLESHOOTING
    clarification_question: Optional[str] = None


class PendingApproval(BaseModel):
    request_id: str
    tool_name: str
    action_type: str = "send_maintenance_email"
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionContext(BaseModel):
    session_id: str
    active_equipment: Optional[str] = None
    active_component: Optional[str] = None
    active_symptom: Optional[str] = None
    active_topic: Optional[str] = None
    last_retrieved_manual_section: Optional[str] = None
    pending_clarification: Optional[PendingClarification] = None
    pending_approval: Optional[PendingApproval] = None
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
