import logging
import re
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Optional
from pydantic import BaseModel


from app.config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_TIMEOUT_SECONDS,
    SMTP_USE_TLS,
    SMTP_USER,
)

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)


class AuthorisedSupplier(BaseModel):
    name: str
    contact_email: str
    is_authorised: bool
    supported_manufacturers: list[str]
    notes: str = ""


# Pre-configured directory of verified suppliers
AUTHORISED_SUPPLIER_DIRECTORY: dict[str, AuthorisedSupplier] = {
    "samsung_parts": AuthorisedSupplier(
        name="Samsung Authorised Parts Centre",
        contact_email="parts-support@samsung-authorized.com",
        is_authorised=True,
        supported_manufacturers=["samsung"],
        notes="Verified OEM replacement components for Samsung laptops and electronics.",
    ),
    "oem_industrial": AuthorisedSupplier(
        name="OEM Certified Industrial Spares",
        contact_email="orders@oem-spares.com",
        is_authorised=True,
        supported_manufacturers=["samsung", "bosch", "siemens", "caterpillar"],
        notes="Verified multi-manufacturer genuine spare parts distributor.",
    ),
    "certified_components": AuthorisedSupplier(
        name="Certified Equipment Components",
        contact_email="sales@certified-components.org",
        is_authorised=True,
        supported_manufacturers=["generic", "multibrand"],
        notes="Authorized distributor for standard mechanical and electrical spares.",
    ),
}


def is_valid_email_address(email: str) -> bool:
    """Validate RFC-compliant email address structure."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_supplier_recipient(
    recipient_email: str,
    manufacturer: Optional[str] = None,
) -> tuple[bool, bool, str]:
    """
    Validate recipient email syntax and authorization status.

    Returns:
        (is_valid_format, is_authorised, advisory_message)
    """
    if not is_valid_email_address(recipient_email):
        return (
            False,
            False,
            f"Invalid recipient email address format: '{recipient_email}'.",
        )

    cleaned_email = recipient_email.strip().lower()

    # Search verified supplier directory
    matched_supplier: Optional[AuthorisedSupplier] = None
    for supplier in AUTHORISED_SUPPLIER_DIRECTORY.values():
        if supplier.contact_email.lower() == cleaned_email:
            matched_supplier = supplier
            break

    if matched_supplier and matched_supplier.is_authorised:
        # Check manufacturer alignment if provided
        if manufacturer:
            m_clean = manufacturer.strip().lower()
            sup_mfg = [m.lower() for m in matched_supplier.supported_manufacturers]
            if m_clean not in sup_mfg and "multibrand" not in sup_mfg:
                return (
                    True,
                    False,
                    f"Warning: Supplier '{matched_supplier.name}' is verified, but "
                    f"is not registered as an authorised distributor for '{manufacturer}'. "
                    f"Please verify authorization before proceeding.",
                )

        return (
            True,
            True,
            f"Verified authorised supplier: {matched_supplier.name}.",
        )

    return (
        True,
        False,
        f"Notice: Recipient '{recipient_email}' is not in the verified authorised "
        f"supplier directory. Please verify that this recipient is an authorised supplier.",
    )


class EmailSendResult(BaseModel):
    success: bool
    provider_message_id: Optional[str] = None
    status_message: str
    error: Optional[str] = None


def send_smtp_email(
    recipient: str,
    subject: str,
    body: str,
    reply_to: Optional[str] = None,
    timeout: int = SMTP_TIMEOUT_SECONDS,
) -> EmailSendResult:
    """
    Send an email via SMTP with TLS encryption and timeout.

    Never logs credentials or full sensitive message content.
    Returns structured delivery status distinguishing accepted-for-sending from failed.
    """
    if not is_valid_email_address(recipient):
        return EmailSendResult(
            success=False,
            error="INVALID_RECIPIENT",
            status_message=f"Recipient address '{recipient}' is invalid.",
        )

    if not SMTP_HOST:
        logger.warning("SMTP_HOST is not configured; cannot send email.")
        return EmailSendResult(
            success=False,
            error="SMTP_NOT_CONFIGURED",
            status_message=(
                "Email provider credentials (SMTP_HOST) are not configured. "
                "Draft has been prepared and previewed, but email cannot be sent."
            ),
        )

    msg = EmailMessage()
    msg["From"] = SMTP_FROM_EMAIL
    msg["To"] = recipient.strip()
    msg["Subject"] = subject.strip()
    msg["Date"] = formatdate(localtime=True)

    domain = SMTP_FROM_EMAIL.split("@")[-1] if "@" in SMTP_FROM_EMAIL else "manualmind.ai"
    msg_id = make_msgid(domain=domain)
    msg["Message-ID"] = msg_id

    if reply_to and is_valid_email_address(reply_to):
        msg["Reply-To"] = reply_to.strip()

    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=timeout) as server:
            if SMTP_USE_TLS:
                server.starttls()

            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)

            server.send_message(msg)

        logger.info(
            "Maintenance email accepted for delivery: %s to %s",
            msg_id,
            recipient,
        )
        return EmailSendResult(
            success=True,
            provider_message_id=msg_id,
            status_message="Accepted for delivery by SMTP provider.",
        )

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP authentication failed for user %s", SMTP_USER)
        return EmailSendResult(
            success=False,
            error="AUTHENTICATION_FAILED",
            status_message=f"SMTP authentication failed: {exc}",
        )
    except smtplib.SMTPException as exc:
        logger.error("SMTP error during email dispatch: %s", exc.__class__.__name__)
        return EmailSendResult(
            success=False,
            error="SMTP_PROVIDER_ERROR",
            status_message=f"SMTP provider rejected message: {exc}",
        )
    except Exception as exc:
        logger.error("Network or connection error during email dispatch: %s", exc.__class__.__name__)
        return EmailSendResult(
            success=False,
            error="CONNECTION_ERROR",
            status_message=f"Connection to SMTP host failed: {exc}",
        )
