from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RouteType(str, Enum):
    DIRECT = "DIRECT"
    RAG = "RAG"
    TOOL = "TOOL"
    CLARIFY = "CLARIFY"


class QueryIntent(str, Enum):
    MANUAL_QUESTION = "manual_question"
    GENERAL_QUESTION = "general_question"
    TROUBLESHOOTING = "troubleshooting"
    MAINTENANCE_EMAIL = "maintenance_email"
    TOOL_ACTION = "tool_action"
    GREETING_OR_CHITCHAT = "greeting_or_chitchat"
    CLARIFICATION_RESPONSE = "clarification_response"
    OTHER = "other"


class ExecutionStep(BaseModel):
    step_number: int
    route: RouteType
    action: str
    tool_name: Optional[str] = None
    description: str


class StructuredRoutingDecision(BaseModel):
    primary_route: RouteType
    intent: QueryIntent = QueryIntent.OTHER
    requires_retrieval: bool = False
    requires_tool: bool = False
    tool_name: Optional[str] = None
    missing_information: list[str] = Field(default_factory=list)
    execution_steps: list[ExecutionStep] = Field(default_factory=list)
    requires_approval: bool = False
    reason: str
    direct_response: Optional[str] = None
    clarification_question: Optional[str] = None

    def __init__(self, **data):
        # Allow passing 'route' as an alias for 'primary_route' for backward compatibility
        if "route" in data and "primary_route" not in data:
            data["primary_route"] = data.pop("route")
        super().__init__(**data)

    @property
    def route(self) -> RouteType:
        """Backward-compatible property mapping primary_route to route."""
        return self.primary_route


# Alias RoutingDecision for backward compatibility across existing services and tests
RoutingDecision = StructuredRoutingDecision
