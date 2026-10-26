from datetime import datetime, timezone
from enum import Enum
import hashlib
import logging
import re
import threading
from typing import Optional
import uuid

from pydantic import BaseModel, Field

from app.services.core.email_service import (
    AUTHORISED_SUPPLIER_DIRECTORY,
    is_valid_email_address,
    send_smtp_email,
    validate_supplier_recipient,
)

logger = logging.getLogger(__name__)



class MaintenanceWorkflowState(str, Enum):
    COLLECTING_DETAILS = "COLLECTING_DETAILS"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    DRAFT_READY = "DRAFT_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SENDING = "SENDING"
    SENT = "SENT"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    SEND_FAILED = "SEND_FAILED"


class MaintenanceEmailRequest(BaseModel):
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    broken_component: Optional[str] = None
    part_number: Optional[str] = "Unknown / To be confirmed by supplier"
    quantity: int = 1
    fault_description: Optional[str] = None
    technician_name: str = "Maintenance Technician"
    reply_to: Optional[str] = None
    supplier_name: Optional[str] = None
    recipient_email: Optional[str] = None
    delivery_location: str = "Main Maintenance Workshop"
    urgency: str = "Normal"
    warranty_status: Optional[str] = None


class MaintenanceEnquiryDraft(BaseModel):
    request_id: str
    state: MaintenanceWorkflowState
    recipient: str
    subject: str
    body: str
    reply_to: Optional[str] = None
    draft_hash: str
    supplier_is_authorised: bool = False
    supplier_advisory: str = ""
    created_at: str
    updated_at: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None


class MaintenanceToolResult(BaseModel):
    status: MaintenanceWorkflowState
    request_id: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    draft: Optional[str] = None
    draft_hash: Optional[str] = None
    requires_user_approval: bool = False
    message: str
    provider_message_id: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)


# In-memory thread-safe store for pending requests
_LOCK = threading.Lock()
_PENDING_REQUESTS: dict[str, MaintenanceEnquiryDraft] = {}


def clear_pending_requests() -> None:
    """Clear in-memory maintenance request store (useful for test isolation)."""
    with _LOCK:
        _PENDING_REQUESTS.clear()


def get_pending_request(request_id: str) -> Optional[MaintenanceEnquiryDraft]:
    """Retrieve a pending maintenance request by its ID."""
    with _LOCK:
        return _PENDING_REQUESTS.get(request_id)


def compute_draft_fingerprint(recipient: str, subject: str, body: str) -> str:
    """
    Compute a SHA-256 fingerprint for approval integrity.
    Ties approval strictly to the exact recipient, subject, and body.
    """
    normalized = f"{recipient.strip().lower()}|{subject.strip()}|{body.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _resolve_supplier(
    recipient_email: Optional[str],
    supplier_name: Optional[str],
    manufacturer: Optional[str],
) -> tuple[Optional[str], Optional[str], bool, str]:
    """
    Resolve recipient email, supplier name, and authorization advisory.

    Returns:
        (resolved_email, resolved_name, is_authorised, advisory)
    """
    if recipient_email and recipient_email.strip():
        email = recipient_email.strip()
        is_valid, is_auth, adv = validate_supplier_recipient(email, manufacturer)
        return email, supplier_name or "Authorized Supplier", is_auth, adv

    # If no email is provided, attempt auto-resolution from directory by manufacturer
    if manufacturer:
        m_lower = manufacturer.strip().lower()
        for supplier in AUTHORISED_SUPPLIER_DIRECTORY.values():
            sup_mfg = [m.lower() for m in supplier.supported_manufacturers]
            if m_lower in sup_mfg:
                return (
                    supplier.contact_email,
                    supplier.name,
                    supplier.is_authorised,
                    f"Auto-selected verified authorised supplier '{supplier.name}' for {manufacturer}.",
                )

    return None, supplier_name, False, "No recipient supplier email provided."


def create_maintenance_email_draft(request: MaintenanceEmailRequest) -> MaintenanceToolResult:
    """
    Validate collected maintenance details and generate an enquiry email draft.

    Enforces:
    - Missing essential details -> NEEDS_MORE_INFORMATION
    - Unknown part numbers are permitted and flagged gracefully
    - Recipient email validated / authorized directory checked
    - Cryptographic fingerprint generated
    - Approval strictly required before sending
    """
    missing_fields: list[str] = []

    if not request.broken_component or not request.broken_component.strip():
        missing_fields.append("broken_component")

    if not (request.device_name and request.device_name.strip()) and not (
        request.model_number and request.model_number.strip()
    ):
        missing_fields.append("device_name or model_number")

    recipient_email, supplier_name, is_auth, advisory = _resolve_supplier(
        request.recipient_email,
        request.supplier_name,
        request.manufacturer,
    )

    if not recipient_email:
        missing_fields.append("recipient_email")
    elif not is_valid_email_address(recipient_email):
        return MaintenanceToolResult(
            status=MaintenanceWorkflowState.NEEDS_MORE_INFORMATION,
            missing_fields=["recipient_email"],
            requires_user_approval=False,
            message=(
                f"The provided recipient email '{recipient_email}' is invalid. "
                "Please provide a valid recipient email address."
            ),
        )

    if missing_fields:
        return MaintenanceToolResult(
            status=MaintenanceWorkflowState.NEEDS_MORE_INFORMATION,
            missing_fields=missing_fields,
            requires_user_approval=False,
            message=(
                f"Missing required information to prepare maintenance enquiry: "
                f"{', '.join(missing_fields)}. Please provide these details."
            ),
        )

    # All critical fields present: build professional email
    part_no = request.part_number.strip() if request.part_number else "Unknown / To be confirmed by supplier"
    mfg = request.manufacturer.strip() if request.manufacturer else "Equipment"
    model = request.model_number.strip() if request.model_number else (request.device_name or "Device")

    subject = f"URGENT: Spare Part RFQ - {mfg} {model} ({request.broken_component.strip()})"

    now_iso = datetime.now(timezone.utc).isoformat()

    body_lines = [
        f"Dear {supplier_name or 'Supplier / Spare Parts Department'},",
        "",
        "We urgently require a price quotation and estimated lead time for a replacement component. "
        "Below are the machine specifications and fault details:",
        "",
        "--- EQUIPMENT IDENTIFICATION ---",
        f"- Equipment / Device: {request.device_name or 'N/A'}",
        f"- Manufacturer: {request.manufacturer or 'N/A'}",
        f"- Model Number: {request.model_number or 'N/A'}",
        "",
        "--- REQUIRED COMPONENT ---",
        f"- Component Name: {request.broken_component}",
        f"- Part Number: {part_no}",
        f"- Quantity Required: {request.quantity}",
        f"- Urgency: {request.urgency}",
        f"- Warranty Status: {request.warranty_status or 'Not specified'}",
        "",
        "--- FAULT DESCRIPTION ---",
        f"{request.fault_description or 'Component has failed during operation and requires replacement.'}",
        "",
        "--- DELIVERY & CONTACT DETAILS ---",
        f"- Delivery Location: {request.delivery_location}",
        f"- Requesting Technician: {request.technician_name}",
        f"- Reply-To Address: {request.reply_to or 'Same as sender'}",
        "",
        "Please confirm availability, unit pricing, and estimated dispatch timeline at your earliest convenience.",
        "",
        "Sincerely,",
        f"{request.technician_name}",
        "ManualMind Maintenance Operations",
    ]
    body = "\n".join(body_lines)

    fingerprint = compute_draft_fingerprint(recipient_email, subject, body)
    request_id = f"req_{uuid.uuid4().hex[:8]}"

    draft = MaintenanceEnquiryDraft(
        request_id=request_id,
        state=MaintenanceWorkflowState.DRAFT_READY,
        recipient=recipient_email,
        subject=subject,
        body=body,
        reply_to=request.reply_to,
        draft_hash=fingerprint,
        supplier_is_authorised=is_auth,
        supplier_advisory=advisory,
        created_at=now_iso,
        updated_at=now_iso,
    )

    with _LOCK:
        _PENDING_REQUESTS[request_id] = draft

    user_message = (
        f"Maintenance enquiry email draft has been prepared.\n\n"
        f"Request ID: {request_id}\n"
        f"Recipient: {recipient_email} ({'Verified Authorised Supplier' if is_auth else 'Unverified Supplier'})\n"
        f"Subject: {subject}\n"
        f"Advisory: {advisory}\n\n"
        f"--- EMAIL PREVIEW ---\n"
        f"{body}\n"
        f"---------------------\n\n"
        f"This email has NOT been sent yet. User approval is strictly required.\n"
        f"To approve and dispatch this email, reply with: APPROVE {request_id}\n"
        f"To reject, reply with: REJECT {request_id}"
    )

    return MaintenanceToolResult(
        status=MaintenanceWorkflowState.DRAFT_READY,
        request_id=request_id,
        recipient=recipient_email,
        subject=subject,
        draft=body,
        draft_hash=fingerprint,
        requires_user_approval=True,
        message=user_message,
    )


def approve_maintenance_email(
    request_id: str,
    approved_hash: Optional[str] = None,
) -> MaintenanceToolResult:
    """
    Approve and send a pending maintenance email enquiry.

    Strict security checks:
    - Verifies request exists
    - Prevents duplicate sends (idempotency)
    - Verifies draft fingerprint if provided
    - Calls SMTP sender service
    - Records provider_message_id on success or sets SEND_FAILED on error
    """
    with _LOCK:
        draft = _PENDING_REQUESTS.get(request_id)
        if not draft:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.SEND_FAILED,
                request_id=request_id,
                requires_user_approval=False,
                message=f"Request ID '{request_id}' not found. Please create a new enquiry.",
            )

        # Idempotency: prevent duplicate dispatch
        if draft.state == MaintenanceWorkflowState.SENT:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.SENT,
                request_id=request_id,
                recipient=draft.recipient,
                subject=draft.subject,
                requires_user_approval=False,
                provider_message_id=draft.provider_message_id,
                message=(
                    f"Email for request '{request_id}' was already sent on {draft.updated_at} "
                    f"(Message-ID: {draft.provider_message_id}). Duplicate send prevented."
                ),
            )

        if draft.state == MaintenanceWorkflowState.APPROVAL_REJECTED:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.APPROVAL_REJECTED,
                request_id=request_id,
                requires_user_approval=False,
                message=f"Request '{request_id}' was previously rejected and cannot be sent.",
            )

        # Integrity check: verify fingerprint
        if approved_hash and approved_hash != draft.draft_hash:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.AWAITING_APPROVAL,
                request_id=request_id,
                draft_hash=draft.draft_hash,
                requires_user_approval=True,
                message=(
                    f"Draft content for '{request_id}' was modified. "
                    "Fingerprint mismatch. Please review the updated draft and re-approve."
                ),
            )

        draft.state = MaintenanceWorkflowState.SENDING
        draft.updated_at = datetime.now(timezone.utc).isoformat()

    # Dispatch email via SMTP
    send_result = send_smtp_email(
        recipient=draft.recipient,
        subject=draft.subject,
        body=draft.body,
        reply_to=draft.reply_to,
    )

    with _LOCK:
        if send_result.success:
            draft.state = MaintenanceWorkflowState.SENT
            draft.provider_message_id = send_result.provider_message_id
            draft.updated_at = datetime.now(timezone.utc).isoformat()
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.SENT,
                request_id=request_id,
                recipient=draft.recipient,
                subject=draft.subject,
                draft=draft.body,
                draft_hash=draft.draft_hash,
                requires_user_approval=False,
                provider_message_id=send_result.provider_message_id,
                message=(
                    f"Maintenance enquiry email successfully sent to {draft.recipient}.\n"
                    f"Provider Message ID: {send_result.provider_message_id}"
                ),
            )
        else:
            draft.state = MaintenanceWorkflowState.SEND_FAILED
            draft.error_message = send_result.status_message
            draft.updated_at = datetime.now(timezone.utc).isoformat()
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.SEND_FAILED,
                request_id=request_id,
                recipient=draft.recipient,
                subject=draft.subject,
                draft=draft.body,
                draft_hash=draft.draft_hash,
                requires_user_approval=True,
                message=(
                    f"Failed to send email to {draft.recipient}: {send_result.status_message}. "
                    "Draft has been retained. You may retry after verifying SMTP settings."
                ),
            )


def reject_maintenance_email(
    request_id: str,
    reason: Optional[str] = None,
) -> MaintenanceToolResult:
    """Explicitly reject a pending maintenance enquiry draft."""
    with _LOCK:
        draft = _PENDING_REQUESTS.get(request_id)
        if not draft:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.APPROVAL_REJECTED,
                request_id=request_id,
                requires_user_approval=False,
                message=f"Request ID '{request_id}' not found.",
            )

        if draft.state == MaintenanceWorkflowState.SENT:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.SENT,
                request_id=request_id,
                requires_user_approval=False,
                message=f"Cannot reject: email for request '{request_id}' has already been dispatched.",
            )

        draft.state = MaintenanceWorkflowState.APPROVAL_REJECTED
        draft.updated_at = datetime.now(timezone.utc).isoformat()
        reason_msg = f" Reason: {reason}" if reason else ""
        return MaintenanceToolResult(
            status=MaintenanceWorkflowState.APPROVAL_REJECTED,
            request_id=request_id,
            requires_user_approval=False,
            message=f"Maintenance enquiry '{request_id}' has been rejected.{reason_msg}",
        )


def update_maintenance_draft(
    request_id: str,
    recipient: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
) -> MaintenanceToolResult:
    """
    Update an existing draft's contents.
    Recomputes hash and strictly resets approval status.
    """
    with _LOCK:
        draft = _PENDING_REQUESTS.get(request_id)
        if not draft:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.NEEDS_MORE_INFORMATION,
                request_id=request_id,
                message=f"Request ID '{request_id}' not found.",
            )

        if draft.state == MaintenanceWorkflowState.SENT:
            return MaintenanceToolResult(
                status=MaintenanceWorkflowState.SENT,
                request_id=request_id,
                message="Cannot edit a draft that has already been dispatched.",
            )

        if recipient:
            draft.recipient = recipient.strip()
        if subject:
            draft.subject = subject.strip()
        if body:
            draft.body = body.strip()

        draft.draft_hash = compute_draft_fingerprint(draft.recipient, draft.subject, draft.body)
        draft.state = MaintenanceWorkflowState.DRAFT_READY
        draft.updated_at = datetime.now(timezone.utc).isoformat()

        return MaintenanceToolResult(
            status=MaintenanceWorkflowState.DRAFT_READY,
            request_id=request_id,
            recipient=draft.recipient,
            subject=draft.subject,
            draft=draft.body,
            draft_hash=draft.draft_hash,
            requires_user_approval=True,
            message=(
                f"Draft '{request_id}' updated successfully. "
                "Because contents were modified, new user approval is required.\n"
                f"To approve, reply with: APPROVE {request_id}"
            ),
        )


MAINTENANCE_APPROVAL_PATTERN = re.compile(
    r"^\s*(?:approve|confirm)\s+(req_[a-zA-Z0-9]+)(?:\s+(?:hash:)?([a-fA-F0-9]+))?\s*$",
    re.IGNORECASE,
)
MAINTENANCE_REJECTION_PATTERN = re.compile(
    r"^\s*(?:reject|cancel)\s+(req_[a-zA-Z0-9]+)(?:\s+(?:reason:\s*)?(.*))?\s*$",
    re.IGNORECASE,
)

KNOWN_MANUFACTURERS = ["samsung", "bosch", "siemens", "caterpillar", "apple", "dell", "hp", "lenovo"]


def parse_maintenance_request_from_text(query: str) -> MaintenanceEmailRequest:
    """
    Extract structured maintenance request attributes from user natural language query.
    Extracts broken component, device/model, manufacturer, recipient email, part number, etc.
    """
    cleaned = query.strip()

    # 1. Extract recipient email if mentioned
    recipient_email = None
    email_match = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", cleaned)
    if email_match:
        recipient_email = email_match.group(1).strip()

    # 2. Extract manufacturer
    manufacturer = None
    mfg_explicit = re.search(r"\b(?:manufacturer|mfg|brand)[:= ]+([a-zA-Z0-9_-]+)", cleaned, re.IGNORECASE)
    if mfg_explicit:
        manufacturer = mfg_explicit.group(1).strip()
    else:
        for m in KNOWN_MANUFACTURERS:
            if re.search(rf"\b{m}\b", cleaned, re.IGNORECASE):
                manufacturer = m.capitalize()
                break

    # 3. Extract model number
    model_number = None
    model_match = re.search(r"\b(?:model|model\s*(?:number|no|#)?)[:= ]+([A-Za-z0-9_-]+)", cleaned, re.IGNORECASE)
    if model_match:
        model_number = model_match.group(1).strip()
    else:
        code_match = re.search(r"\b([A-Z0-9]{2,}[0-9]+[A-Z0-9]*)\b", cleaned)
        if code_match:
            candidate = code_match.group(1).strip()
            if not candidate.lower().startswith("req_") and not candidate.isdigit():
                model_number = candidate

    # 4. Extract broken component
    broken_component = None
    comp_explicit = re.search(r"\b(?:component|part)[:= ]+([^,\n;]+)", cleaned, re.IGNORECASE)
    if comp_explicit:
        broken_component = comp_explicit.group(1).strip()
    else:
        comp_match = re.search(
            r"\b(?:broken|defective|damaged|faulty|replacement)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)*?)(?:\s+(?:on|in|for|part|at|model|#|\.|,)|$)",
            cleaned,
            re.IGNORECASE,
        )
        if comp_match:
            cand = comp_match.group(1).strip()
            if cand.lower() not in {"email", "maintenance", "part", "component"}:
                if cand.lower() in {"montherboad", "motherbord", "motheboard"}:
                    cand = "Motherboard"
                broken_component = cand

    # 5. Extract part number
    part_number = "Unknown / To be confirmed by supplier"
    part_match = re.search(r"\bpart\s*(?:number|no|#)[:= ]+([A-Za-z0-9_-]+)", cleaned, re.IGNORECASE)
    if part_match:
        part_number = part_match.group(1).strip()

    # 6. Extract quantity
    quantity = 1
    qty_match = re.search(r"\b(?:qty|quantity)[:= ]+(\d+)", cleaned, re.IGNORECASE)
    if qty_match:
        try:
            quantity = int(qty_match.group(1))
        except ValueError:
            quantity = 1

    # 7. Extract device name
    device_name = None
    dev_match = re.search(r"\bdevice[:= ]+([^,\n;]+)", cleaned, re.IGNORECASE)
    if dev_match:
        device_name = dev_match.group(1).strip()
    elif manufacturer or model_number:
        device_name = f"{manufacturer or ''} {model_number or ''}".strip() or None

    # 8. Extract fault description
    fault_desc = None
    fault_match = re.search(r"\b(?:fault|issue|description)[:= ]+([^;\n]+)", cleaned, re.IGNORECASE)
    if fault_match:
        fault_desc = fault_match.group(1).strip()

    # 9. Extract technician name
    technician_name = "Maintenance Technician"
    tech_match = re.search(r"\b(?:technician|tech)[:= ]+([^,\n;]+)", cleaned, re.IGNORECASE)
    if tech_match:
        technician_name = tech_match.group(1).strip()

    # 10. Extract supplier name
    supplier_name = None
    sup_match = re.search(r"\b(?:supplier|company|vendor|manufacturer)[:= ]+([^,\n;]+)", cleaned, re.IGNORECASE)
    if sup_match:
        supplier_name = sup_match.group(1).strip()
    elif re.search(r"\b(?:the\s+)?company\b", cleaned, re.IGNORECASE):
        supplier_name = "Company / Supplier"

    # 11. Extract urgency
    urgency = "Normal"
    if re.search(r"\b(?:urgent|critical|high\s+priority|emergency)\b", cleaned, re.IGNORECASE):
        urgency = "Urgent"

    return MaintenanceEmailRequest(
        device_name=device_name,
        manufacturer=manufacturer,
        model_number=model_number,
        broken_component=broken_component,
        part_number=part_number,
        quantity=quantity,
        fault_description=fault_desc,
        technician_name=technician_name,
        recipient_email=recipient_email,
        supplier_name=supplier_name,
        urgency=urgency,
    )


def handle_maintenance_tool_query(query: str) -> MaintenanceToolResult:
    """
    Dispatcher for maintenance email actions from queries:
    - Approval commands (APPROVE req_xxx)
    - Rejection commands (REJECT req_xxx)
    - Draft creation queries
    """
    approval_match = MAINTENANCE_APPROVAL_PATTERN.search(query)
    if approval_match:
        req_id = approval_match.group(1).strip()
        approved_hash = approval_match.group(2).strip() if approval_match.group(2) else None
        return approve_maintenance_email(req_id, approved_hash)

    rejection_match = MAINTENANCE_REJECTION_PATTERN.search(query)
    if rejection_match:
        req_id = rejection_match.group(1).strip()
        reason = rejection_match.group(2).strip() if rejection_match.group(2) else None
        return reject_maintenance_email(req_id, reason)

    req = parse_maintenance_request_from_text(query)
    return create_maintenance_email_draft(req)

