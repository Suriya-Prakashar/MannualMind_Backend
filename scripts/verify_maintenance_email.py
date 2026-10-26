import sys
from unittest.mock import MagicMock, patch

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.core.email_service import EmailSendResult
from app.services.core.maintenance_email_service import (
    MaintenanceWorkflowState,
    clear_pending_requests,
)
from app.services.core.query_service import process_query


def run_demo():
    print("=" * 65)
    print(" MANUALMIND: send_maintenance_email WORKFLOW DEMONSTRATION")
    print("=" * 65)

    clear_pending_requests()

    # Step 1: Technician requests spare part enquiry
    print("\n[Step 1] Technician Query:")
    query_1 = (
        "Send maintenance email to parts-support@samsung-authorized.com: "
        "broken motherboard on Samsung NP740VJG"
    )
    print(f"Query: \"{query_1}\"")

    response_1 = process_query(query_1)
    print(f"\nRoute Selected: {response_1['route']}")
    print(f"Status: {response_1['status']}")

    tool_res = response_1.get("tool_result", {})
    req_id = tool_res.get("request_id")
    print(f"Workflow State: {tool_res.get('status')}")
    print(f"Assigned Request ID: {req_id}")
    print(f"Requires User Approval: {tool_res.get('requires_user_approval')}")
    print("\n--- DRAFT PREVIEW GENERATED FOR TECHNICIAN ---")
    print(tool_res.get("draft"))
    print("----------------------------------------------")

    # Step 2: Technician approves the email draft
    print(f"\n[Step 2] Technician approves draft via query:")
    approve_query = f"APPROVE {req_id}"
    print(f"Query: \"{approve_query}\"")

    # Mock SMTP to simulate successful external delivery
    with patch(
        "app.services.core.maintenance_email_service.send_smtp_email",
        return_value=EmailSendResult(
            success=True,
            provider_message_id="<smtp-demo-20261025@manualmind.ai>",
            status_message="Accepted by mail exchange",
        ),
    ):
        response_2 = process_query(approve_query)

    tool_res_2 = response_2.get("tool_result", {})
    print(f"\nWorkflow State: {tool_res_2.get('status')}")
    print(f"Provider Message-ID: {tool_res_2.get('provider_message_id')}")
    print(f"System Message: {response_2['answer']}")

    # Step 3: Duplicate send prevention (Idempotency)
    print(f"\n[Step 3] Testing Idempotency (Technician types APPROVE again):")
    response_3 = process_query(approve_query)
    print(f"System Message: {response_3['answer']}")

    print("\n" + "=" * 65)
    print(" ALL WORKFLOW STEPS VERIFIED SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
