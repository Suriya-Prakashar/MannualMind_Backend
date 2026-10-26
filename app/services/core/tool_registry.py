from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    requires_approval: bool = False
    required_parameters: list[str] = Field(default_factory=list)
    optional_parameters: list[str] = Field(default_factory=list)
    schema_details: dict[str, Any] = Field(default_factory=dict)


# Pre-configured registry of valid application tools
REGISTERED_TOOLS: dict[str, ToolDefinition] = {
    "send_maintenance_email": ToolDefinition(
        name="send_maintenance_email",
        description="Draft a spare part or maintenance quotation enquiry email to an authorized supplier for broken equipment.",
        requires_approval=True,
        required_parameters=["broken_component", "device_name_or_model", "recipient_email"],
        optional_parameters=[
            "part_number",
            "quantity",
            "fault_description",
            "technician_name",
            "reply_to",
            "urgency",
            "delivery_location",
            "warranty_status",
            "manufacturer",
        ],
        schema_details={
            "broken_component": "Name of the damaged or defective part needing replacement",
            "device_name_or_model": "Device identification (model number or device name)",
            "recipient_email": "Destination supplier or OEM contact email address",
        },
    ),
    "approve_maintenance_email": ToolDefinition(
        name="approve_maintenance_email",
        description="Approve and execute the dispatch of a pending maintenance email enquiry via SMTP.",
        requires_approval=False,
        required_parameters=["request_id"],
        optional_parameters=["approved_hash"],
        schema_details={
            "request_id": "Unique request ID of the pending draft (e.g., req_xxxxxxxx)",
            "approved_hash": "Optional SHA-256 fingerprint of the draft being confirmed",
        },
    ),
    "reject_maintenance_email": ToolDefinition(
        name="reject_maintenance_email",
        description="Explicitly reject and cancel a pending maintenance email enquiry draft.",
        requires_approval=False,
        required_parameters=["request_id"],
        optional_parameters=["reason"],
        schema_details={
            "request_id": "Unique request ID of the pending draft (e.g., req_xxxxxxxx)",
            "reason": "Optional rationale for rejecting the draft",
        },
    ),
}

# Known tool intents requested by users that are external or unintegrated
UNSUPPORTED_TOOL_CATALOG: dict[str, str] = {
    "create_maintenance_ticket": "Jira / ITSM ticketing integrations are not currently registered or configured.",
    "check_inventory": "External ERP and warehouse inventory lookup integrations are not currently registered.",
    "export_to_jira": "Direct Jira work order export is not currently registered.",
    "order_external_parts": "Direct e-commerce procurement gateway is not currently registered; please use 'send_maintenance_email' to contact suppliers directly.",
}


class ToolRegistry:
    """Central registry and validator for all ManualMind backend tools."""

    @classmethod
    def get_tool(cls, tool_name: str) -> Optional[ToolDefinition]:
        """Retrieve tool definition if registered."""
        if not tool_name:
            return None
        return REGISTERED_TOOLS.get(tool_name.strip())

    @classmethod
    def is_registered(cls, tool_name: str) -> bool:
        """Check if a tool exists in the registry."""
        return cls.get_tool(tool_name) is not None

    @classmethod
    def is_unsupported(cls, tool_name: str) -> bool:
        """Check if a requested tool is known but currently unintegrated."""
        if not tool_name:
            return False
        return tool_name.strip() in UNSUPPORTED_TOOL_CATALOG

    @classmethod
    def get_unsupported_reason(cls, tool_name: str) -> str:
        """Return clear advisory reason why tool cannot be executed."""
        if not tool_name:
            return "Requested tool is not supported."
        return UNSUPPORTED_TOOL_CATALOG.get(
            tool_name.strip(),
            f"Tool '{tool_name}' is not registered in the application tool registry.",
        )

    @classmethod
    def list_tools(cls) -> list[ToolDefinition]:
        """List all available tools in the registry."""
        return list(REGISTERED_TOOLS.values())

    @classmethod
    def validate_tool_arguments(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate provided arguments against tool schema.

        Returns:
            (is_valid, missing_required_fields)
        """
        tool = cls.get_tool(tool_name)
        if not tool:
            return False, [f"Unknown tool: '{tool_name}'"]

        missing = []
        for param in tool.required_parameters:
            if param not in arguments or not arguments[param]:
                missing.append(param)

        return len(missing) == 0, missing
