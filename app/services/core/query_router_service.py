import logging
import re
from typing import Any, Optional

from app.models.routing import (
    ExecutionStep,
    QueryIntent,
    RouteType,
    RoutingDecision,
    StructuredRoutingDecision,
)
from app.models.session import SessionContext
from app.services.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# Exact greetings and pleasantries (normalized)
GREETING_PATTERNS = {
    "hello",
    "hi",
    "hey",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "how are you doing",
    "who are you",
    "what are you",
    "what can you do",
}

THANKS_PATTERNS = {
    "thank you",
    "thanks",
    "thanks a lot",
    "thank you very much",
    "thx",
}

FAREWELL_PATTERNS = {
    "bye",
    "goodbye",
    "see you",
    "see you later",
    "have a good day",
}

# Technical terms indicating manual-specific topics
TECHNICAL_INDICATORS = {
    "what",
    "how",
    "why",
    "where",
    "when",
    "which",
    "replace",
    "install",
    "repair",
    "torque",
    "capacity",
    "manual",
    "specs",
    "specification",
    "specifications",
    "error",
    "code",
    "oil",
    "battery",
    "filter",
    "fuse",
    "model",
    "engine",
    "problem",
    "guide",
    "steps",
    "procedure",
}

# General engineering and AI definitions (answered directly without manual retrieval)
GENERAL_CONCEPTS: dict[str, str] = {
    "llm": (
        "An LLM (Large Language Model) is an artificial intelligence model trained on massive amounts "
        "of text data to understand, generate, and reason with human language."
    ),
    "rag": (
        "RAG (Retrieval-Augmented Generation) is an AI architecture that enhances language models by "
        "first retrieving relevant factual passages from a knowledge base (such as technical manuals), "
        "and then passing them to the model to generate accurate, grounded answers."
    ),
    "preventive_maintenance": (
        "Preventive maintenance is the scheduled, proactive inspection, servicing, and cleaning of "
        "equipment at predetermined intervals to prevent unexpected failures and prolong operating life."
    ),
    "ram_vs_rom": (
        "RAM (Random Access Memory) is high-speed, volatile working memory used by the operating system "
        "and active applications, losing data when powered off. ROM (Read-Only Memory) is non-volatile "
        "permanent memory used to store essential firmware and boot instructions."
    ),
    "api": (
        "An API (Application Programming Interface) is a set of defined rules and protocols that allows "
        "different software applications to communicate and exchange data with one another."
    ),
    "cooling_fan_general": (
        "In general, a cooling fan uses electric motor-driven aerodynamic blades to generate airflow, "
        "dissipating heat from hot components (such as CPUs, heatsinks, or radiators) via forced convection."
    ),
}

# Regex patterns for maintenance email workflow
MAINTENANCE_APPROVAL_PATTERN = re.compile(
    r"^\s*(?:approve|confirm)\s+(req_[a-zA-Z0-9]+)(?:\s+(?:hash:)?([a-fA-F0-9]+))?\s*$",
    re.IGNORECASE,
)
MAINTENANCE_REJECTION_PATTERN = re.compile(
    r"^\s*(?:reject|cancel)\s+(req_[a-zA-Z0-9]+)(?:\s+(?:reason:\s*)?(.*))?\s*$",
    re.IGNORECASE,
)
MAINTENANCE_EMAIL_PATTERNS = [
    r"\bmaintenance\s+email\b",
    r"\b(?:send|draft|prepare|create|write|compose|generate)\s+(?:an?\s+)?(?:maintenance|supplier|parts?|spare\s+parts?|quote|rfq)\s+email\b",
    r"\b(?:send|draft|prepare|create|write|compose|generate)\s+(?:an?\s+)?(?:email|mail|message)\s+(?:to|for)\s+(?:the\s+)?(?:company|supplier|manufacturer|vendor|oem|parts\s+centre|support|service\s+centre)\b",
    r"\b(?:send|draft|prepare|create|write|compose|generate)\s+(?:an?\s+)?(?:email|mail|message)\b.*?\b(?:broken|damaged|faulty|defective|replacement|spare|repair)\b",
    r"\b(?:broken|damaged|faulty|defective|replacement|spare|repair)\b.*?\b(?:send|draft|prepare|create|write|compose|generate)\s+(?:an?\s+)?(?:email|mail|message)\b",
    r"\b(?:email|contact)\s+(?:the\s+)?(?:supplier|manufacturer|parts\s+centre|oem|company|vendor)\b",
    r"\b(?:order|request)\s+(?:a\s+)?(?:replacement\s+parts?|replacement|spare\s+parts?|parts?)\s+(?:from|via)\s+(?:the\s+)?(?:supplier|manufacturer|company|vendor|oem)\b",
]

# Regex patterns for personal/general correspondence outside maintenance scope
PERSONAL_EMAIL_PATTERNS = [
    r"\b(?:write|compose|send|draft|make)\s+(?:an?\s+)?(?:personal\s+)?(?:email|mail|message|letter)\s+(?:to|for)\s+(?:my\s+)?(?:friend|frnd|pal|buddy|family|mom|dad|brother|sister|wife|husband|colleague|cousin|boss)\b",
    r"\b(?:write|compose|draft)\s+(?:a\s+)?personal\s+email\b",
    r"\b(?:email|mail|message)\s+(?:to|for)\s+(?:my\s+)?(?:friend|frnd)\b",
]

PERSONAL_EMAIL_RESPONSE = (
    "Hello! I am ManualMind, your technical manual and equipment maintenance assistant. "
    "I specialize in looking up technical specifications and drafting official spare part enquiry "
    "emails to authorized suppliers. I don't write personal emails for friends or general correspondence, "
    "but I would be happy to help you with equipment troubleshooting, manual queries, or parts requests!"
)

# Regex patterns for external tool action requests
TOOL_PATTERNS = [
    r"\b(?:send\s+an?\s+email|send\s+email|email\s+this|email\s+to)\b",
    r"\b(?:create|open|log|raise)\s+(?:an?\s+)?(?:[a-zA-Z]+\s+)?ticket\b",
    r"\b(?:order\s+(?:a\s+)?(?:part|replacement)|order\s+parts)\b",
    r"\b(?:check\s+inventory|check\s+.*?\binventory|look\s*up\s+(?:in\s+)?(?:external\s+)?inventory)\b",
    r"\b(?:export\s+.*?\bto\s+jira|export\s+to\s+jira|create\s+(?:a\s+)?work\s+order)\b",
]

TOOL_UNSUPPORTED_MESSAGE = (
    "External action tools (such as sending emails, creating tickets, or "
    "querying external inventory systems) are not currently supported."
)

# Multi-step query patterns
MULTI_STEP_RAG_TOOL_PATTERN = re.compile(
    r"\b(?:find|look\s*up|get|check)\b.*?\b(?:in\s+the\s+manual|in\s+manual|from\s+manual)\b.*?\b(?:and\s+)?(?:draft|email|send\s+email|contact\s+supplier)\b",
    re.IGNORECASE,
)
MULTI_STEP_DIRECT_RAG_PATTERN = re.compile(
    r"\bwhat\s+is\b.*?\band\s+(?:what\s+does\s+)?(?:my|the|this)\s+(?:repair\s+)?manual\s+say\b",
    re.IGNORECASE,
)

# Ambiguous queries that require clarification before proceeding
AMBIGUOUS_PATTERNS = [
    r"^(?:please\s+)?(?:fix|repair|replace|check|order|inspect)\s+it\b",
    r"^(?:it\s+is|it\s*s|it)\s+(?:broken|not\s+working|damaged|faulty|won\s*t\s+turn\s+on|won\s*t\s+start|won\s*t\s+work|stopped\s+working)\b",
    r"^(?:how\s+to\s+fix|help\s+me\s+fix)\b",
    r"^(?:something\s+is\s+wrong|not\s+working)$",
]

# Conversational responses for approval workflows
AFFIRMATIVE_APPROVAL_PATTERN = re.compile(
    r"^\s*(?:yes|yep|yeah|sure|confirm|confirmed|approve|approved|go\s+ahead|proceed|please\s+send(?:\s+it)?|send\s+it)\b",
    re.IGNORECASE,
)
NEGATIVE_CANCELLATION_PATTERN = re.compile(
    r"^\s*(?:no|nope|cancel|cancelled|don'?t\s+send|do\s+not\s+send|reject|stop|abort)\b",
    re.IGNORECASE,
)

# Pronoun indicators in follow-up queries
PRONOUN_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:it|its|this\s+part|this\s+machine|this\s+device|the\s+same|them)\b",
    re.IGNORECASE,
)


def _normalize_query(query: str) -> str:
    """Normalize query by stripping punctuation and extra whitespace for phrase matching."""
    cleaned = re.sub(r"[^\w\s]", " ", query.lower())
    return " ".join(cleaned.split())


def _match_general_concept(normalized: str) -> Optional[tuple[str, str]]:
    """
    Check if query is asking for a general definition/concept without manual reference.
    Returns (concept_key, explanation) or None.
    """
    if re.search(r"\b(?:what\s+is\s+(?:an?\s+)?llm|explain\s+llm)\b", normalized):
        return "llm", GENERAL_CONCEPTS["llm"]
    if re.search(r"\b(?:what\s+is\s+rag|explain\s+rag)\b", normalized):
        return "rag", GENERAL_CONCEPTS["rag"]
    if re.search(r"\b(?:what\s+is\s+preventive\s+maintenance|explain\s+preventive\s+maintenance)\b", normalized):
        return "preventive_maintenance", GENERAL_CONCEPTS["preventive_maintenance"]
    if re.search(r"\b(?:difference\s+between\s+ram\s+and\s+rom|ram\s+(?:vs|versus)\s+rom)\b", normalized):
        return "ram_vs_rom", GENERAL_CONCEPTS["ram_vs_rom"]
    if re.search(r"\b(?:what\s+(?:an?\s+)?api\s+does|what\s+is\s+(?:an?\s+)?api|explain\s+(?:what\s+(?:an?\s+)?)?apis?)\b", normalized):
        return "api", GENERAL_CONCEPTS["api"]
    if re.search(r"\bhow\s+does\s+(?:a\s+)?cooling\s+fan\s+work\s+in\s+general\b", normalized):
        return "cooling_fan_general", GENERAL_CONCEPTS["cooling_fan_general"]
    return None


def classify_route(
    query: str,
    session_context: Optional[Union[dict[str, Any], SessionContext]] = None,
) -> StructuredRoutingDecision:
    """
    Intelligently analyze query semantics, context, required sources, and outcomes
    to produce a StructuredRoutingDecision (DIRECT, RAG, TOOL, or CLARIFY).
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    cleaned_raw = query.strip()
    normalized = _normalize_query(cleaned_raw)
    words = set(normalized.split())

    # Extract session context variables if provided
    active_equipment: Optional[str] = None
    active_component: Optional[str] = None
    active_symptom: Optional[str] = None
    pending_clarification_data: Optional[dict[str, Any]] = None
    pending_approval_data: Optional[dict[str, Any]] = None

    if session_context:
        if isinstance(session_context, dict):
            active_equipment = session_context.get("active_equipment")
            active_component = session_context.get("active_component")
            active_symptom = session_context.get("active_symptom")
            p_clar = session_context.get("pending_clarification")
            if isinstance(p_clar, dict):
                pending_clarification_data = p_clar
            elif p_clar and hasattr(p_clar, "model_dump"):
                pending_clarification_data = p_clar.model_dump()
            elif p_clar:
                pending_clarification_data = dict(p_clar)

            p_appr = session_context.get("pending_approval")
            if isinstance(p_appr, dict):
                pending_approval_data = p_appr
            elif p_appr and hasattr(p_appr, "model_dump"):
                pending_approval_data = p_appr.model_dump()
            elif p_appr:
                pending_approval_data = dict(p_appr)
        else:
            active_equipment = getattr(session_context, "active_equipment", None)
            active_component = getattr(session_context, "active_component", None)
            active_symptom = getattr(session_context, "active_symptom", None)
            p_clar = getattr(session_context, "pending_clarification", None)
            if p_clar and hasattr(p_clar, "model_dump"):
                pending_clarification_data = p_clar.model_dump()
            p_appr = getattr(session_context, "pending_approval", None)
            if p_appr and hasattr(p_appr, "model_dump"):
                pending_approval_data = p_appr.model_dump()

    has_manual_reference = bool(
        re.search(
            r"\b(?:this\s+manual|the\s+manual|my\s+manual|repair\s+guide|in\s+manual|page\s+\d+|on\s+page)\b",
            normalized,
        )
    )

    # 1. Explicit maintenance tool commands (APPROVE / REJECT req_xxx)
    if MAINTENANCE_APPROVAL_PATTERN.search(cleaned_raw) or MAINTENANCE_REJECTION_PATTERN.search(cleaned_raw):
        is_approve = bool(MAINTENANCE_APPROVAL_PATTERN.search(cleaned_raw))
        action_name = "approve_maintenance_email" if is_approve else "reject_maintenance_email"
        return StructuredRoutingDecision(
            primary_route=RouteType.TOOL,
            intent=QueryIntent.MAINTENANCE_EMAIL,
            requires_retrieval=False,
            requires_tool=True,
            tool_name="send_maintenance_email",
            requires_approval=False,
            reason="User issued maintenance email approval or rejection workflow command.",
            execution_steps=[
                ExecutionStep(
                    step_number=1,
                    route=RouteType.TOOL,
                    action=action_name,
                    tool_name="send_maintenance_email",
                    description="Execute approval/rejection transition for pending draft.",
                )
            ],
        )

    # 1b. Conversational response to a pending tool approval
    if pending_approval_data:
        req_id = pending_approval_data.get("request_id", "pending")
        tool_name = pending_approval_data.get("tool_name", "send_maintenance_email")
        if AFFIRMATIVE_APPROVAL_PATTERN.search(cleaned_raw):
            return StructuredRoutingDecision(
                primary_route=RouteType.TOOL,
                intent=QueryIntent.MAINTENANCE_EMAIL,
                requires_retrieval=False,
                requires_tool=True,
                tool_name=tool_name,
                requires_approval=False,
                reason=f"User affirmed execution of pending maintenance request ({req_id}).",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.TOOL,
                        action="approve_maintenance_email",
                        tool_name=tool_name,
                        description=f"Execute pending maintenance email dispatch ({req_id}) upon user confirmation.",
                    )
                ],
            )
        if NEGATIVE_CANCELLATION_PATTERN.search(cleaned_raw):
            return StructuredRoutingDecision(
                primary_route=RouteType.DIRECT,
                intent=QueryIntent.TOOL_ACTION,
                requires_retrieval=False,
                requires_tool=False,
                reason=f"User cancelled execution of pending maintenance request ({req_id}).",
                direct_response="Understood. The pending maintenance request has been cancelled and will not be sent.",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.DIRECT,
                        action="cancel_pending_action",
                        description="Cancel pending maintenance action upon user cancellation.",
                    )
                ],
            )

    # 2. Multi-step orchestration: Manual evidence lookup + Supplier email drafting
    if MULTI_STEP_RAG_TOOL_PATTERN.search(normalized):
        return StructuredRoutingDecision(
            primary_route=RouteType.RAG,
            intent=QueryIntent.MAINTENANCE_EMAIL,
            requires_retrieval=True,
            requires_tool=True,
            tool_name="send_maintenance_email",
            requires_approval=True,
            reason="Multi-step workflow: retrieve component part number from manual, then prepare maintenance email draft.",
            execution_steps=[
                ExecutionStep(
                    step_number=1,
                    route=RouteType.RAG,
                    action="retrieve_manual_evidence",
                    description="Retrieve component part number and specifications from technical manual chunks.",
                ),
                ExecutionStep(
                    step_number=2,
                    route=RouteType.TOOL,
                    action="draft_maintenance_email",
                    tool_name="send_maintenance_email",
                    description="Draft spare parts quotation request email to authorized supplier.",
                ),
            ],
        )

    # 3. Multi-step orchestration: Direct general definition + Manual-grounded troubleshooting
    if MULTI_STEP_DIRECT_RAG_PATTERN.search(normalized):
        return StructuredRoutingDecision(
            primary_route=RouteType.RAG,
            intent=QueryIntent.MANUAL_QUESTION,
            requires_retrieval=True,
            requires_tool=False,
            reason="Multi-step query: explain general technical concept directly, then retrieve manual-grounded troubleshooting guidance.",
            execution_steps=[
                ExecutionStep(
                    step_number=1,
                    route=RouteType.DIRECT,
                    action="explain_concept",
                    description="Provide general definition of the requested concept.",
                ),
                ExecutionStep(
                    step_number=2,
                    route=RouteType.RAG,
                    action="retrieve_manual_guidance",
                    description="Retrieve overheating troubleshooting guidance from technical manual chunks.",
                ),
            ],
        )

    # 4. Maintenance spare parts email generation requests
    for pattern in MAINTENANCE_EMAIL_PATTERNS:
        if re.search(pattern, normalized):
            return StructuredRoutingDecision(
                primary_route=RouteType.TOOL,
                intent=QueryIntent.MAINTENANCE_EMAIL,
                requires_retrieval=False,
                requires_tool=True,
                tool_name="send_maintenance_email",
                requires_approval=True,
                reason="User requested maintenance spare parts enquiry email workflow.",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.TOOL,
                        action="draft_maintenance_email",
                        tool_name="send_maintenance_email",
                        description="Parse request and prepare supplier quotation enquiry draft.",
                    )
                ],
            )

    # 5. Personal / general correspondence requests
    for pattern in PERSONAL_EMAIL_PATTERNS:
        if re.search(pattern, normalized):
            return StructuredRoutingDecision(
                primary_route=RouteType.DIRECT,
                intent=QueryIntent.GENERAL_QUESTION,
                requires_retrieval=False,
                requires_tool=False,
                reason="User requested a personal or general email outside of technical manual scope.",
                direct_response=PERSONAL_EMAIL_RESPONSE,
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.DIRECT,
                        action="clarify_scope",
                        description="Politely explain assistant's specialization in manuals and maintenance.",
                    )
                ],
            )

    # 6. Ambiguous queries requiring clarification (CLARIFY route)
    for pattern in AMBIGUOUS_PATTERNS:
        if re.search(pattern, normalized):
            if active_equipment or active_component:
                context_str = active_equipment or active_component
                return StructuredRoutingDecision(
                    primary_route=RouteType.RAG,
                    intent=QueryIntent.TROUBLESHOOTING,
                    requires_retrieval=True,
                    requires_tool=False,
                    reason=f"Ambiguous query '{cleaned_raw}' resolved using active session context: '{context_str}'.",
                    execution_steps=[
                        ExecutionStep(
                            step_number=1,
                            route=RouteType.RAG,
                            action="manual_troubleshooting_search",
                            description=f"Search troubleshooting procedures for {context_str}.",
                        )
                    ],
                )
            return StructuredRoutingDecision(
                primary_route=RouteType.CLARIFY,
                intent=QueryIntent.TROUBLESHOOTING,
                requires_retrieval=False,
                requires_tool=False,
                missing_information=["equipment_name_or_model", "problem_description"],
                reason="The query is ambiguous and does not identify the target equipment, model, or specific defect.",
                clarification_question="Could you please specify which machine, device, or component you need assistance with?",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.CLARIFY,
                        action="request_clarification",
                        description="Prompt user to specify equipment or issue details.",
                    )
                ],
            )

    # 6b. Conversational response resolving a prior pending clarification
    if pending_clarification_data:
        orig_q = pending_clarification_data.get("original_query", "")
        concept_match = _match_general_concept(normalized)
        is_greeting = normalized in GREETING_PATTERNS or any(
            normalized.startswith(f"{g} ") for g in ("hello", "hi", "hey")
        )
        if not concept_match and not is_greeting:
            return StructuredRoutingDecision(
                primary_route=RouteType.RAG,
                intent=QueryIntent.CLARIFICATION_RESPONSE,
                requires_retrieval=True,
                requires_tool=False,
                reason=f"User provided clarification ('{cleaned_raw}') resolving pending question for: '{orig_q}'.",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.RAG,
                        action="manual_retrieval",
                        description=f"Search technical manual combining clarified context: '{cleaned_raw} {orig_q}'.",
                    )
                ],
            )

    # 6c. Pronoun follow-ups referring to active session context
    if (active_equipment or active_component) and PRONOUN_FOLLOWUP_PATTERN.search(normalized):
        context_str = active_equipment or active_component
        if any(re.search(p, normalized) for p in MAINTENANCE_EMAIL_PATTERNS):
            return StructuredRoutingDecision(
                primary_route=RouteType.TOOL,
                intent=QueryIntent.MAINTENANCE_EMAIL,
                requires_retrieval=False,
                requires_tool=True,
                tool_name="send_maintenance_email",
                requires_approval=True,
                reason=f"Maintenance draft requested for active session context: '{context_str}'.",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.TOOL,
                        action="draft_maintenance_email",
                        tool_name="send_maintenance_email",
                        description=f"Prepare spare parts enquiry email for {context_str}.",
                    )
                ],
            )
        if any(w in words for w in {"replace", "install", "clean", "torque", "procedure", "spec", "specs", "capacity", "cost", "price", "where", "how", "what", "remove", "disassemble"}):
            return StructuredRoutingDecision(
                primary_route=RouteType.RAG,
                intent=QueryIntent.MANUAL_QUESTION,
                requires_retrieval=True,
                requires_tool=False,
                reason=f"Follow-up query '{cleaned_raw}' grounded in active session context: '{context_str}'.",
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.RAG,
                        action="manual_retrieval",
                        description=f"Search manual for follow-up details on {context_str}.",
                    )
                ],
            )

    # 7. Generic external tool action intents
    for pattern in TOOL_PATTERNS:
        if re.search(pattern, normalized):
            unsupported_tool = None
            if re.search(r"\b(?:ticket)\b", normalized):
                unsupported_tool = "create_maintenance_ticket"
            elif re.search(r"\b(?:inventory)\b", normalized):
                unsupported_tool = "check_inventory"
            elif re.search(r"\b(?:jira)\b", normalized):
                unsupported_tool = "export_to_jira"

            unsupported_detail = (
                ToolRegistry.get_unsupported_reason(unsupported_tool)
                if unsupported_tool
                else "User requested an external action tool not supported by current integrations."
            )
            return StructuredRoutingDecision(
                primary_route=RouteType.TOOL,
                intent=QueryIntent.TOOL_ACTION,
                requires_retrieval=False,
                requires_tool=False,
                tool_name=None,
                reason=unsupported_detail,
                direct_response=TOOL_UNSUPPORTED_MESSAGE,
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.TOOL,
                        action="report_unsupported_tool",
                        description="Explain that external integration is not currently supported.",
                    )
                ],
            )

    # 8. General conceptual definitions (DIRECT route without manual retrieval)
    if not has_manual_reference:
        concept_match = _match_general_concept(normalized)
        if concept_match:
            concept_key, answer_text = concept_match
            return StructuredRoutingDecision(
                primary_route=RouteType.DIRECT,
                intent=QueryIntent.GENERAL_QUESTION,
                requires_retrieval=False,
                requires_tool=False,
                reason=f"General engineering definition/concept ({concept_key}) answered directly without consulting technical manuals.",
                direct_response=answer_text,
                execution_steps=[
                    ExecutionStep(
                        step_number=1,
                        route=RouteType.DIRECT,
                        action="direct_explanation",
                        description=f"Provide general knowledge explanation for {concept_key}",
                    )
                ],
            )

    # 9. Conversational pleasantries, greetings, thanks, and farewells
    # 9. Conversational pleasantries, greetings, thanks, and farewells
    is_greeting_start = normalized in GREETING_PATTERNS or any(
        normalized.startswith(f"{g} ") or normalized.startswith(f"{g},")
        for g in ("hello", "hi", "hey", "good morning", "good afternoon", "good evening")
    )
    has_actual_equipment_or_manual_topic = bool(
        has_manual_reference
        or re.search(r"\b(?:replace|install|repair|filter|oil|fan|battery|screen|specs?|procedure|torque|diagram|manual|error|broken|leak|model|np\d+)\b", normalized)
    )

    if (is_greeting_start and not has_actual_equipment_or_manual_topic) or normalized in GREETING_PATTERNS:
        return StructuredRoutingDecision(
            primary_route=RouteType.DIRECT,
            intent=QueryIntent.GREETING_OR_CHITCHAT,
            requires_retrieval=False,
            requires_tool=False,
            reason="Conversational greeting or general pleasantry.",
            direct_response=(
                "Hello! I am ManualMind, your technical manual assistant. "
                "How can I help you with your manuals or equipment today?"
            ),
        )

    # Check DIRECT thanks
    if normalized in THANKS_PATTERNS or any(
        normalized.startswith(f"{t} ") for t in ("thanks", "thank you")
    ):
        return StructuredRoutingDecision(
            primary_route=RouteType.DIRECT,
            intent=QueryIntent.GREETING_OR_CHITCHAT,
            requires_retrieval=False,
            requires_tool=False,
            reason="Conversational expression of gratitude.",
            direct_response=(
                "You are welcome! Let me know if you need any more "
                "assistance with your manuals."
            ),
        )

    # Check DIRECT farewells
    if normalized in FAREWELL_PATTERNS or any(
        normalized.startswith(f"{f} ") for f in ("bye", "goodbye")
    ):
        return StructuredRoutingDecision(
            primary_route=RouteType.DIRECT,
            intent=QueryIntent.GREETING_OR_CHITCHAT,
            requires_retrieval=False,
            requires_tool=False,
            reason="Conversational farewell.",
            direct_response=(
                "Goodbye! Feel free to ask anytime you need information "
                "from your technical manuals."
            ),
        )

    # 10. Technical questions and manual-grounded troubleshooting (RAG route)
    is_troubleshooting = bool(
        re.search(
            r"\b(?:error|troubleshoot(?:ing)?|fault|problem|overheating|not\s+working|broken|leak(?:ing|s)?|warning)\b",
            normalized,
        )
    )
    selected_intent = (
        QueryIntent.TROUBLESHOOTING if is_troubleshooting else QueryIntent.MANUAL_QUESTION
    )

    return StructuredRoutingDecision(
        primary_route=RouteType.RAG,
        intent=selected_intent,
        requires_retrieval=True,
        requires_tool=False,
        reason="Technical question requiring information retrieval from manual chunks.",
        execution_steps=[
            ExecutionStep(
                step_number=1,
                route=RouteType.RAG,
                action="hybrid_retrieval_and_answer",
                description="Search manual chunks with hybrid search and generate grounded answer.",
            )
        ],
    )
