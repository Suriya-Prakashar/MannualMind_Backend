from datetime import datetime, timezone
import re
import threading
from typing import Any, Optional
import uuid

from app.models.routing import QueryIntent, RouteType
from app.models.session import (
    ConversationTurn,
    PendingApproval,
    PendingClarification,
    SessionContext,
)

# Common regex patterns to detect models, components, and symptoms in user queries
MODEL_PATTERN = re.compile(
    r"\b(?:Samsung\s+[A-Za-z0-9\-]+|NP\d+[A-Z0-9]*|Galaxy\s+Book\s*[A-Za-z0-9]*)\b",
    re.IGNORECASE,
)
COMPONENT_PATTERN = re.compile(
    r"\b(?:cooling\s+fan|fan|battery|ram|rom|ssd|hard\s+drive|motherboard|filter|hydraulic\s+pump|pump|spark\s+plug|motor|alternator|screen|display|keyboard|trackpad|power\s+supply)\b",
    re.IGNORECASE,
)
SYMPTOM_PATTERN = re.compile(
    r"\b(?:won'?t\s+turn\s+on|overheating|not\s+working|broken|leak|black\s+screen|not\s+charging|beeping|vibrating|blue\s+screen|shutting\s+down|smoke|error\s+[A-Za-z0-9\-]+)\b",
    re.IGNORECASE,
)


class SessionService:
    """
    Thread-safe in-memory service managing multi-turn conversational session context,
    active equipment tracking, pending clarifications, and tool approval workflows.
    """

    def __init__(self, max_turns: int = 20):
        self._sessions: dict[str, SessionContext] = {}
        self._lock = threading.Lock()
        self._max_turns = max_turns

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionContext:
        """
        Retrieve an existing session or initialize a new one with a unique session ID.
        """
        with self._lock:
            if not session_id:
                session_id = f"sess_{uuid.uuid4().hex[:12]}"

            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)

            return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """
        Retrieve session state for a given session_id if it exists.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def extract_context_entities(self, text: str) -> dict[str, Optional[str]]:
        """
        Inspect text to extract equipment/model names, components, and symptoms.
        """
        entities: dict[str, Optional[str]] = {
            "equipment": None,
            "component": None,
            "symptom": None,
        }
        model_match = MODEL_PATTERN.search(text)
        if model_match:
            entities["equipment"] = model_match.group(0).strip()

        comp_match = COMPONENT_PATTERN.search(text)
        if comp_match:
            entities["component"] = comp_match.group(0).strip()

        symp_matches = SYMPTOM_PATTERN.findall(text)
        if symp_matches:
            unique_symps = list(dict.fromkeys(s.strip() for s in symp_matches))
            entities["symptom"] = ", ".join(unique_symps)

        return entities

    def add_turn(
        self,
        session_id: str,
        user_query: str,
        assistant_response: Optional[str] = None,
        route: RouteType = RouteType.RAG,
        intent: Optional[QueryIntent] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> SessionContext:
        """
        Record a conversation turn and update active context entities from user input.
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)

            session = self._sessions[session_id]

            turn = ConversationTurn(
                user_query=user_query,
                assistant_response=assistant_response,
                route=route,
                intent=intent,
                metadata=metadata or {},
            )
            session.turns.append(turn)

            # Keep only the last N turns (sliding window)
            if len(session.turns) > self._max_turns:
                session.turns = session.turns[-self._max_turns :]

            # Update active context entities if present
            entities = self.extract_context_entities(user_query)
            if entities["equipment"]:
                session.active_equipment = entities["equipment"]
            if entities["component"]:
                session.active_component = entities["component"]
            if entities["symptom"]:
                session.active_symptom = entities["symptom"]

            session.updated_at = datetime.now(timezone.utc)
            return session

    def update_active_context(
        self,
        session_id: str,
        equipment: Optional[str] = None,
        component: Optional[str] = None,
        symptom: Optional[str] = None,
        topic: Optional[str] = None,
        last_retrieved_section: Optional[str] = None,
    ) -> SessionContext:
        """
        Explicitly update specific active context variables for a session.
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)

            session = self._sessions[session_id]
            if equipment is not None:
                session.active_equipment = equipment
            if component is not None:
                session.active_component = component
            if symptom is not None:
                session.active_symptom = symptom
            if topic is not None:
                session.active_topic = topic
            if last_retrieved_section is not None:
                session.last_retrieved_manual_section = last_retrieved_section

            session.updated_at = datetime.now(timezone.utc)
            return session

    def set_pending_clarification(
        self,
        session_id: str,
        missing_fields: list[str],
        original_query: str,
        intent: QueryIntent = QueryIntent.TROUBLESHOOTING,
        clarification_question: Optional[str] = None,
    ) -> SessionContext:
        """
        Record that a clarification question was asked and wait for user's response.
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)

            session = self._sessions[session_id]
            session.pending_clarification = PendingClarification(
                missing_fields=missing_fields,
                original_query=original_query,
                intent=intent,
                clarification_question=clarification_question,
            )
            session.updated_at = datetime.now(timezone.utc)
            return session

    def clear_pending_clarification(self, session_id: str) -> SessionContext:
        """
        Clear pending clarification state after the user provides missing information.
        """
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.pending_clarification = None
                session.updated_at = datetime.now(timezone.utc)
                return session
            return self.get_or_create_session(session_id)

    def set_pending_approval(
        self,
        session_id: str,
        request_id: str,
        tool_name: str,
        payload: dict[str, Any],
        action_type: str = "send_maintenance_email",
    ) -> SessionContext:
        """
        Record that an action requires user approval before execution.
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)

            session = self._sessions[session_id]
            session.pending_approval = PendingApproval(
                request_id=request_id,
                tool_name=tool_name,
                action_type=action_type,
                payload=payload,
            )
            session.updated_at = datetime.now(timezone.utc)
            return session

    def get_pending_approval(self, session_id: str) -> Optional[PendingApproval]:
        """
        Get the currently pending approval for a session if one exists.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            return session.pending_approval if session else None

    def clear_pending_approval(self, session_id: str) -> SessionContext:
        """
        Clear pending approval state after execution or cancellation.
        """
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.pending_approval = None
                session.updated_at = datetime.now(timezone.utc)
                return session
            return self.get_or_create_session(session_id)

    def get_recent_history(
        self,
        session_id: str,
        limit: int = 5,
    ) -> list[ConversationTurn]:
        """
        Retrieve the last N completed conversation turns for prompt context memory.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.turns:
                return []
            return list(session.turns[-limit:])

    def clear_all_sessions(self) -> None:
        """
        Clear all active sessions (primarily for unit tests).
        """
        with self._lock:
            self._sessions.clear()


# Global singleton instance
session_service = SessionService()
