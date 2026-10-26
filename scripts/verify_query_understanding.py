"""
Verification Script for ManualMind Intelligent User Query Understanding & Routing Engine
Demonstrates all 6 core categories, multi-step orchestration, and multi-turn session tracking.
"""

import json
import os
import sys
from unittest.mock import patch

# Ensure root backend directory is in python module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.routing import RouteType
from app.services.core.email_service import EmailSendResult
from app.services.core.maintenance_email_service import clear_pending_requests
from app.services.core.query_router_service import classify_route
from app.services.core.query_service import process_query
from app.services.core.session_service import session_service


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_turn(turn_label: str, query: str, result: dict):
    print(f"\n[{turn_label}] User Query: \"{query}\"")
    print(f"  -> Primary Route : {result.get('route')}")
    print(f"  -> Status        : {result.get('status')}")
    if result.get("clarification_question"):
        print(f"  -> Clarification : {result.get('clarification_question')}")
    if result.get("missing_information"):
        print(f"  -> Missing Info  : {result.get('missing_information')}")
    if result.get("answer"):
        first_line = result['answer'].split('\n')[0][:90]
        print(f"  -> Answer        : {first_line}...")
    if result.get("tool_result"):
        t_res = result['tool_result']
        print(f"  -> Tool Result   : Status={t_res.get('status')}, ReqID={t_res.get('request_id')}, ApprovalReq={t_res.get('requires_user_approval')}")


def main():
    session_service.clear_all_sessions()
    clear_pending_requests()

    # ---------------------------------------------------------------------------
    # Demonstration 1: Category 1 (Direct Answers)
    # ---------------------------------------------------------------------------
    print_section("DEMONSTRATION 1: DIRECT ANSWERS (Concepts & Pleasantries)")
    q1 = "What is an LLM?"
    res1 = process_query(q1)
    print_turn("Turn 1", q1, res1)
    assert res1["route"] == "DIRECT"

    q2 = "Hello ManualMind, how are you today?"
    res2 = process_query(q2)
    print_turn("Turn 2", q2, res2)
    assert res2["route"] == "DIRECT"

    q3 = "Can you write an email for my friend?"
    res3 = process_query(q3)
    print_turn("Turn 3", q3, res3)
    assert res3["route"] == "DIRECT"

    # ---------------------------------------------------------------------------
    # Demonstration 2: Category 2 (Manual-Grounded RAG)
    # ---------------------------------------------------------------------------
    print_section("DEMONSTRATION 2: MANUAL-GROUNDED RETRIEVAL (RAG)")
    mock_chunks = [
        {
            "chunk_id": "chunk_manual_001",
            "page_number": 15,
            "text": "The engine oil capacity for this model is 4.5 litres of synthetic 5W-30.",
        }
    ]
    with patch("app.services.core.query_service.retrieve_chunks", return_value=mock_chunks), \
         patch("app.services.core.query_service.generate_answer", return_value="The recommended engine oil capacity is 4.5 litres of synthetic 5W-30."):
        q_rag = "What is the recommended engine oil capacity in this manual?"
        res_rag = process_query(q_rag)
        print_turn("Turn 1", q_rag, res_rag)
        assert res_rag["route"] == "RAG"
        assert len(res_rag["sources"]) == 1

    # ---------------------------------------------------------------------------
    # Demonstration 3: Category 3 (Action Execution & Unsupported Tools)
    # ---------------------------------------------------------------------------
    print_section("DEMONSTRATION 3: TOOL ACTIONS (Registered & Unsupported)")
    q_unsupported = "Create a ticket in Jira for this issue"
    res_unsupported = process_query(q_unsupported)
    print_turn("Turn 1", q_unsupported, res_unsupported)
    assert res_unsupported["route"] == "TOOL"
    assert "not currently supported" in res_unsupported["answer"]

    q_tool_draft = "Draft a maintenance email to vendor@samsung.com: broken fan on Samsung NP550"
    res_tool_draft = process_query(q_tool_draft)
    print_turn("Turn 2", q_tool_draft, res_tool_draft)
    assert res_tool_draft["route"] == "TOOL"
    req_id = res_tool_draft["tool_result"]["request_id"]

    # ---------------------------------------------------------------------------
    # Demonstration 4: Category 4, 5, 6 (Multi-Turn, Clarification, & Natural Approval)
    # ---------------------------------------------------------------------------
    print_section("DEMONSTRATION 4: MULTI-TURN SESSION CONTEXT & CLARIFICATION")
    session_id = "sess_live_demo_01"

    # Turn 1: User gives ambiguous symptom lacking model
    t1_q = "It won't turn on"
    t1_res = process_query(t1_q, session_id=session_id)
    print_turn("Multi-Turn Step 1 (Ambiguous -> CLARIFY)", t1_q, t1_res)
    assert t1_res["route"] == "CLARIFY"

    # Turn 2: User answers clarification question with equipment model
    mock_diag_chunks = [
        {
            "chunk_id": "chunk_diag_550",
            "page_number": 42,
            "text": "For Samsung NP550 failure to power on, perform hard power reset by disconnecting AC and battery.",
        }
    ]
    with patch("app.services.core.query_service.retrieve_chunks", return_value=mock_diag_chunks), \
         patch("app.services.core.query_service.generate_answer", return_value="For Samsung NP550 power failure, perform a hard reset by disconnecting AC adapter and battery."):
        t2_q = "Samsung NP550"
        t2_res = process_query(t2_q, session_id=session_id)
        print_turn("Multi-Turn Step 2 (Clarification Answer -> RAG)", t2_q, t2_res)
        assert t2_res["route"] == "RAG"

    # Turn 3: User asks follow-up with pronoun "its" (context carryover)
    with patch("app.services.core.query_service.retrieve_chunks", return_value=mock_diag_chunks), \
         patch("app.services.core.query_service.generate_answer", return_value="The Samsung NP550 cooling fan is located in the top-right corner of the chassis."):
        t3_q = "Where is its cooling fan located?"
        t3_res = process_query(t3_q, session_id=session_id)
        print_turn("Multi-Turn Step 3 (Pronoun Follow-up -> RAG)", t3_q, t3_res)
        assert t3_res["route"] == "RAG"

    # Turn 4: User asks to order replacement part for it
    t4_q = "Draft an email to order a replacement for it"
    t4_res = process_query(t4_q, session_id=session_id)
    print_turn("Multi-Turn Step 4 (Order Draft for Active Equipment -> TOOL)", t4_q, t4_res)
    assert t4_res["route"] == "TOOL"
    assert t4_res["requires_approval"] is True
    pending_id = t4_res["tool_result"]["request_id"]

    # Turn 5: User gives conversational natural approval
    with patch("app.services.core.maintenance_email_service.send_smtp_email", return_value=EmailSendResult(success=True, provider_message_id="<demo-msg-101@manualmind.ai>", status_message="Sent")):
        t5_q = "Yes, please send it"
        t5_res = process_query(t5_q, session_id=session_id)
        print_turn("Multi-Turn Step 5 (Natural Language Approval -> TOOL Sent)", t5_q, t5_res)
        assert t5_res["route"] == "TOOL"
        assert t5_res["tool_result"]["status"] == "SENT"
        assert t5_res["requires_approval"] is False

    print("\n" + "=" * 70)
    print("  ALL VERIFICATION SCENARIOS COMPLETED SUCCESSFULLY!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
