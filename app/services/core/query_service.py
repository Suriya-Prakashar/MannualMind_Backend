from collections.abc import Generator
from typing import Any, Optional


from app.services.core.answer_generation_service import (
    FALLBACK_ANSWER,
    generate_answer,
    generate_answer_stream,
)
from app.services.core.image_resolver_service import (
    collect_unique_images_from_chunks,
    resolve_chunk_images,
)
from app.services.core.query_router_service import (
    RouteType,
    classify_route,
)
from app.services.core.retrieval_service import retrieve_chunks
from app.services.core.session_service import session_service


def _build_sources_and_images(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract sources with image references and unique image catalog from chunks."""
    all_images = collect_unique_images_from_chunks(chunks)
    sources = []
    for chunk in chunks:
        src: dict[str, Any] = {
            "chunk_id": chunk.get("chunk_id", ""),
            "page_number": chunk.get("page_number", 0),
            "snippet": chunk.get("text", "").strip(),
        }
        chunk_imgs = chunk.get("images") or resolve_chunk_images(chunk)
        if chunk_imgs:
            src["images"] = chunk_imgs
        sources.append(src)
    return sources, all_images


def process_query(query: str, session_id: Optional[str] = None) -> dict[str, Any]:
    """
    Process a user query through the Query Router and execute the selected route
    (DIRECT, CLARIFY, TOOL, or RAG) with optional multi-turn session tracking (5 turns memory).
    """
    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    # Retrieve or create session context if session_id is provided
    session = None
    if session_id:
        session = session_service.get_or_create_session(session_id)

    decision = classify_route(cleaned_query, session_context=session)

    # 1. DIRECT Route (General Knowledge, scope clarifications, greetings, pleasantries)
    if decision.primary_route == RouteType.DIRECT:
        answer = decision.direct_response or "Direct answer generated."
        if session:
            session_service.add_turn(
                session_id=session.session_id,
                user_query=cleaned_query,
                assistant_response=answer,
                route=RouteType.DIRECT,
                intent=decision.intent,
            )
        resp: dict[str, Any] = {
            "query": cleaned_query,
            "route": RouteType.DIRECT.value,
            "answer": answer,
            "sources": [],
            "status": "success",
            "message": "Direct response generated.",
        }
        if session_id:
            resp["session_id"] = session_id
            resp["primary_route"] = RouteType.DIRECT.value
            resp["intent"] = decision.intent.value
            resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
        return resp

    # 2. CLARIFY Route (Ambiguous or missing necessary context)
    if decision.primary_route == RouteType.CLARIFY:
        clarification_q = (
            decision.clarification_question
            or "Could you please specify which machine, device, or component you need assistance with?"
        )
        if session:
            session_service.set_pending_clarification(
                session_id=session.session_id,
                missing_fields=decision.missing_information,
                original_query=cleaned_query,
                intent=decision.intent,
                clarification_question=clarification_q,
            )
            session_service.add_turn(
                session_id=session.session_id,
                user_query=cleaned_query,
                assistant_response=clarification_q,
                route=RouteType.CLARIFY,
                intent=decision.intent,
            )
        resp = {
            "query": cleaned_query,
            "route": RouteType.CLARIFY.value,
            "answer": clarification_q,
            "sources": [],
            "status": "success",
            "message": "Clarification required from user.",
            "clarification_question": clarification_q,
            "missing_information": decision.missing_information,
        }
        if session_id:
            resp["session_id"] = session_id
            resp["primary_route"] = RouteType.CLARIFY.value
            resp["intent"] = decision.intent.value
            resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
        return resp

    # 3. TOOL Route (Maintenance email workflow & unsupported tool reporting)
    if decision.primary_route == RouteType.TOOL:
        if decision.tool_name == "send_maintenance_email":
            from app.services.core.maintenance_email_service import (
                MaintenanceWorkflowState,
                handle_maintenance_tool_query,
            )

            tool_query = cleaned_query
            if session and session.pending_approval and not decision.requires_approval:
                req_id = session.pending_approval.request_id
                if req_id.lower() not in cleaned_query.lower():
                    tool_query = f"APPROVE {req_id}"
            elif session and (session.active_equipment or session.active_component):
                context_parts = []
                if session.active_equipment and session.active_equipment.lower() not in cleaned_query.lower():
                    context_parts.append(session.active_equipment)
                if session.active_component and session.active_component.lower() not in cleaned_query.lower():
                    context_parts.append(session.active_component)
                if context_parts:
                    tool_query = f"{cleaned_query} for {' '.join(context_parts)}"

            tool_result = handle_maintenance_tool_query(tool_query)
            status_str = "error" if tool_result.status == MaintenanceWorkflowState.SEND_FAILED else "success"

            if session:
                if tool_result.requires_user_approval and tool_result.request_id:
                    session_service.set_pending_approval(
                        session_id=session.session_id,
                        request_id=tool_result.request_id,
                        tool_name="send_maintenance_email",
                        payload=tool_result.model_dump(),
                    )
                elif tool_result.status in (
                    MaintenanceWorkflowState.SENT,
                    MaintenanceWorkflowState.APPROVAL_REJECTED,
                ):
                    session_service.clear_pending_approval(session.session_id)

                session_service.add_turn(
                    session_id=session.session_id,
                    user_query=cleaned_query,
                    assistant_response=tool_result.message,
                    route=RouteType.TOOL,
                    intent=decision.intent,
                )

            resp = {
                "query": cleaned_query,
                "route": RouteType.TOOL.value,
                "answer": tool_result.message,
                "sources": [],
                "status": status_str,
                "message": f"Maintenance tool status: {tool_result.status.value}",
                "tool_result": tool_result.model_dump(),
            }
            if session_id:
                resp["session_id"] = session_id
                resp["primary_route"] = RouteType.TOOL.value
                resp["intent"] = decision.intent.value
                resp["requires_approval"] = tool_result.requires_user_approval
                resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
            return resp

        # Unsupported tool reporting
        answer = decision.direct_response
        if session:
            session_service.add_turn(
                session_id=session.session_id,
                user_query=cleaned_query,
                assistant_response=answer,
                route=RouteType.TOOL,
                intent=decision.intent,
            )
        resp = {
            "query": cleaned_query,
            "route": RouteType.TOOL.value,
            "answer": answer,
            "sources": [],
            "status": "success",
            "message": "Tool action not supported.",
        }
        if session_id:
            resp["session_id"] = session_id
            resp["primary_route"] = RouteType.TOOL.value
            resp["intent"] = decision.intent.value
            resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
        return resp

    # 4. RAG Route (Manual retrieval, grounded answer, multimodal images, 5-turn history)
    retrieval_query = cleaned_query
    if session and session.pending_clarification:
        orig_q = session.pending_clarification.original_query
        retrieval_query = f"{cleaned_query} {orig_q}"
        session_service.clear_pending_clarification(session.session_id)

    chunks = retrieve_chunks(retrieval_query)

    if not chunks:
        resp = {
            "query": cleaned_query,
            "route": RouteType.RAG.value,
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "status": "success",
            "message": "No matching manual chunks found.",
        }
        if session_id:
            resp["session_id"] = session_id
            resp["primary_route"] = RouteType.RAG.value
            resp["intent"] = decision.intent.value
            resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
        return resp

    sources, all_images = _build_sources_and_images(chunks)

    # Extract last 5 turns of conversation context
    conversation_history = None
    if session:
        conversation_history = session_service.get_recent_history(session.session_id, limit=5)

    if conversation_history:
        answer = generate_answer(retrieval_query, chunks, conversation_history=conversation_history)
    else:
        answer = generate_answer(retrieval_query, chunks)

    # Multi-step plan execution: Step 1 (RAG) + Step 2 (Tool drafting)
    if decision.requires_tool and decision.tool_name == "send_maintenance_email":
        from app.services.core.maintenance_email_service import handle_maintenance_tool_query

        tool_query = f"Send maintenance email for {cleaned_query}. Findings: {answer}"
        tool_result = handle_maintenance_tool_query(tool_query)
        combined_answer = (
            f"{answer}\n\n"
            f"---\n"
            f"**Automated Step: Maintenance Email Draft Prepared**\n"
            f"{tool_result.message}"
        )
        if session:
            if tool_result.requires_user_approval and tool_result.request_id:
                session_service.set_pending_approval(
                    session_id=session.session_id,
                    request_id=tool_result.request_id,
                    tool_name="send_maintenance_email",
                    payload=tool_result.model_dump(),
                )
            session_service.add_turn(
                session_id=session.session_id,
                user_query=cleaned_query,
                assistant_response=combined_answer,
                route=RouteType.RAG,
                intent=decision.intent,
            )

        resp = {
            "query": cleaned_query,
            "route": RouteType.RAG.value,
            "answer": combined_answer,
            "sources": sources,
            "status": "success",
            "message": "Multi-step lookup and tool draft completed.",
            "tool_result": tool_result.model_dump(),
        }
        if all_images:
            resp["images"] = all_images
        if session_id:
            resp["session_id"] = session_id
            resp["primary_route"] = RouteType.RAG.value
            resp["intent"] = decision.intent.value
            resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
        return resp

    # Standard single-step RAG
    if session:
        session_service.add_turn(
            session_id=session.session_id,
            user_query=cleaned_query,
            assistant_response=answer,
            route=RouteType.RAG,
            intent=decision.intent,
        )

    resp = {
        "query": cleaned_query,
        "route": RouteType.RAG.value,
        "answer": answer,
        "sources": sources,
        "status": "success",
        "message": "Answer generated successfully.",
    }
    if all_images:
        resp["images"] = all_images
    if session_id:
        resp["session_id"] = session_id
        resp["primary_route"] = RouteType.RAG.value
        resp["intent"] = decision.intent.value
        resp["execution_steps"] = [s.model_dump() for s in decision.execution_steps]
    return resp


def process_query_stream(
    query: str,
    session_id: Optional[str] = None,
) -> Generator[dict[str, Any], None, None]:
    """
    Stream answer tokens word-by-word / chunk-by-chunk using Server-Sent Events (SSE).
    Yields dictionary events:
      - {'event': 'metadata', 'data': {...}}
      - {'event': 'token', 'data': {'token': str}}
      - {'event': 'done', 'data': {...}}
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    session = None
    if session_id:
        session = session_service.get_or_create_session(session_id)

    decision = classify_route(cleaned_query, session_context=session)

    # 1. Non-RAG routes: yield complete answer token stream
    if decision.primary_route != RouteType.RAG:
        full_res = process_query(cleaned_query, session_id=session_id)
        yield {
            "event": "metadata",
            "data": {
                "route": full_res["route"],
                "status": full_res["status"],
                "session_id": session_id,
                "sources": full_res.get("sources", []),
                "images": full_res.get("images", []),
                "clarification_question": full_res.get("clarification_question"),
                "missing_information": full_res.get("missing_information", []),
                "tool_result": full_res.get("tool_result"),
            },
        }

        # Stream words
        words = full_res["answer"].split(" ")
        for idx, word in enumerate(words):
            token_str = word if idx == len(words) - 1 else word + " "
            yield {"event": "token", "data": {"token": token_str}}

        yield {"event": "done", "data": {"route": full_res["route"], "answer": full_res["answer"]}}
        return

    # 2. RAG Route with token-by-token streaming
    retrieval_query = cleaned_query
    if session and session.pending_clarification:
        orig_q = session.pending_clarification.original_query
        retrieval_query = f"{cleaned_query} {orig_q}"
        session_service.clear_pending_clarification(session.session_id)

    chunks = retrieve_chunks(retrieval_query)
    sources, all_images = _build_sources_and_images(chunks)

    yield {
        "event": "metadata",
        "data": {
            "route": RouteType.RAG.value,
            "status": "success",
            "session_id": session_id,
            "sources": sources,
            "images": all_images,
        },
    }

    if not chunks:
        yield {"event": "token", "data": {"token": FALLBACK_ANSWER}}
        yield {"event": "done", "data": {"route": RouteType.RAG.value, "answer": FALLBACK_ANSWER}}
        return

    # Multi-turn history (last 5 turns)
    conversation_history = None
    if session:
        conversation_history = session_service.get_recent_history(session.session_id, limit=5)

    accumulated_tokens: list[str] = []
    for token in generate_answer_stream(retrieval_query, chunks, conversation_history=conversation_history):
        accumulated_tokens.append(token)
        yield {"event": "token", "data": {"token": token}}

    final_answer = "".join(accumulated_tokens).strip()

    if session:
        session_service.add_turn(
            session_id=session.session_id,
            user_query=cleaned_query,
            assistant_response=final_answer,
            route=RouteType.RAG,
            intent=decision.intent,
        )

    yield {
        "event": "done",
        "data": {
            "route": RouteType.RAG.value,
            "answer": final_answer,
            "sources": sources,
            "images": all_images,
        },
    }