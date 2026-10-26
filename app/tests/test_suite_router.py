"""
Test Suite: Query Understanding, Intent Classification & Routing Engine
Consolidates and validates:
- RouteType, QueryIntent, and StructuredRoutingDecision domain models
- ToolRegistry (registered and unsupported catalog)
- Direct routing (greetings, general technical concepts, out of scope)
- RAG routing (manual-grounded questions & troubleshooting)
- Ambiguous query handling and CLARIFY route
- Tool action routing and unsupported tool handling
- Multi-step reasoning and plan generation
"""
from unittest.mock import patch
import pytest

from app.models.routing import (
    ExecutionStep,
    QueryIntent,
    RouteType,
    RoutingDecision,
    StructuredRoutingDecision,
)
from app.services.core.email_service import EmailSendResult
from app.services.core.maintenance_email_service import clear_pending_requests
from app.services.core.query_router_service import classify_route
from app.services.core.query_service import process_query
from app.services.core.session_service import session_service
from app.services.core.tool_registry import (
    REGISTERED_TOOLS,
    UNSUPPORTED_TOOL_CATALOG,
    ToolDefinition,
    ToolRegistry,
)


@pytest.fixture(autouse=True)
def clean_test_environment():
    session_service.clear_all_sessions()
    clear_pending_requests()
    yield
    session_service.clear_all_sessions()
    clear_pending_requests()


# ===========================================================================
# 1. Routing Schemas & Tool Registry
# ===========================================================================
def test_route_type_and_intent_enums():
    assert RouteType.DIRECT.value == "DIRECT"
    assert RouteType.RAG.value == "RAG"
    assert RouteType.TOOL.value == "TOOL"
    assert RouteType.CLARIFY.value == "CLARIFY"

    assert QueryIntent.MANUAL_QUESTION.value == "manual_question"
    assert QueryIntent.GENERAL_QUESTION.value == "general_question"
    assert QueryIntent.TROUBLESHOOTING.value == "troubleshooting"
    assert QueryIntent.MAINTENANCE_EMAIL.value == "maintenance_email"
    assert QueryIntent.TOOL_ACTION.value == "tool_action"
    assert QueryIntent.GREETING_OR_CHITCHAT.value == "greeting_or_chitchat"
    assert QueryIntent.CLARIFICATION_RESPONSE.value == "clarification_response"


def test_structured_routing_decision_properties():
    step = ExecutionStep(
        step_number=1,
        route=RouteType.RAG,
        action="lookup",
        description="Lookup manual details",
    )
    decision = StructuredRoutingDecision(
        primary_route=RouteType.RAG,
        intent=QueryIntent.MANUAL_QUESTION,
        requires_retrieval=True,
        execution_steps=[step],
        reason="Manual question asked",
    )
    assert decision.route == RouteType.RAG
    assert decision.primary_route == RouteType.RAG
    assert len(decision.execution_steps) == 1


def test_tool_registry_lookups():
    tool = ToolRegistry.get_tool("send_maintenance_email")
    assert tool is not None
    assert tool.requires_approval is True
    assert "broken_component" in tool.required_parameters

    assert ToolRegistry.is_registered("send_maintenance_email") is True
    assert ToolRegistry.is_registered("non_existent_tool") is False
    assert ToolRegistry.is_unsupported("check_inventory") is True
    assert "warehouse" in ToolRegistry.get_unsupported_reason("check_inventory").lower()


# ===========================================================================
# 2. Direct Answers (Greetings & General Concepts)
# ===========================================================================
@pytest.mark.parametrize(
    "greeting_query",
    ["Hello", "Hi there", "Good morning", "Hey ManualMind", "how are you"],
)
def test_direct_route_greetings(greeting_query):
    decision = classify_route(greeting_query)
    assert decision.primary_route == RouteType.DIRECT
    assert decision.intent == QueryIntent.GREETING_OR_CHITCHAT
    assert decision.requires_retrieval is False
    assert decision.direct_response is not None


@pytest.mark.parametrize(
    ("query", "expected_concept"),
    [
        ("What is an LLM?", "llm"),
        ("Explain RAG in simple English", "rag"),
        ("What is preventive maintenance?", "preventive_maintenance"),
        ("What is the difference between RAM and ROM?", "ram_vs_rom"),
        ("Explain what an API does.", "api"),
        ("How does a cooling fan work in general?", "cooling_fan_general"),
    ],
)
def test_direct_route_general_concepts(query, expected_concept):
    decision = classify_route(query)
    assert decision.primary_route == RouteType.DIRECT
    assert decision.intent == QueryIntent.GENERAL_QUESTION
    assert decision.requires_retrieval is False
    assert decision.direct_response is not None


# ===========================================================================
# 3. RAG Route (Manual-Grounded Retrieval)
# ===========================================================================
@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("What is the recommended oil capacity in this manual?", QueryIntent.MANUAL_QUESTION),
        ("Which error codes are documented for this machine?", QueryIntent.TROUBLESHOOTING),
        ("Explain the procedure for replacing the cooling fan.", QueryIntent.MANUAL_QUESTION),
        ("What torque specification does the manual provide?", QueryIntent.MANUAL_QUESTION),
        ("Summarise the troubleshooting procedure on page 15.", QueryIntent.TROUBLESHOOTING),
    ],
)
def test_rag_route_manual_queries(query, expected_intent):
    decision = classify_route(query)
    assert decision.primary_route == RouteType.RAG
    assert decision.intent == expected_intent
    assert decision.requires_retrieval is True
    assert decision.requires_tool is False


# ===========================================================================
# 4. Ambiguous Queries & Clarifications
# ===========================================================================
@pytest.mark.parametrize(
    "ambiguous_query",
    [
        "It won't turn on",
        "It is not working",
        "It is broken",
        "Help me fix it",
        "Something is wrong",
        "Please inspect it",
    ],
)
def test_clarify_route_for_ambiguous_queries(ambiguous_query):
    decision = classify_route(ambiguous_query)
    assert decision.primary_route == RouteType.CLARIFY
    assert decision.requires_retrieval is False
    assert decision.requires_tool is False
    assert len(decision.missing_information) > 0
    assert decision.clarification_question is not None


# ===========================================================================
# 5. Tool Action & Unsupported Tools
# ===========================================================================
def test_tool_route_maintenance_email():
    query = "Send maintenance email to parts@supplier.com for broken motor"
    decision = classify_route(query)
    assert decision.primary_route == RouteType.TOOL
    assert decision.intent == QueryIntent.MAINTENANCE_EMAIL
    assert decision.requires_tool is True
    assert decision.tool_name == "send_maintenance_email"


@pytest.mark.parametrize(
    "unsupported_query",
    [
        "Create a ticket in Jira for this issue",
        "Open a ticket with technical support",
        "Check external warehouse inventory for spark plugs",
        "Order a replacement battery from Amazon",
    ],
)
def test_unsupported_tools_handled_cleanly(unsupported_query):
    decision = classify_route(unsupported_query)
    assert decision.primary_route == RouteType.TOOL
    assert decision.requires_tool is False
    assert decision.tool_name is None
    assert "not currently supported" in decision.direct_response

