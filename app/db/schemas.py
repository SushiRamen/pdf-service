from pydantic import BaseModel, Field
from db.models import DocumentStatus
import datetime
from typing import Any, Optional

# ── Inbound (n8n → service) ─────────────────────────────────────────────────

class DocumentCreateRequest(BaseModel):
    """
    POST /api/v1/documents/create

    template_parameters structure:
      {
        "facility": { "Name": "...", "Phone": "..." },
        "tenant":   { "Name": "...", "Email": "...", "CellPhone": "..." },
        "space":    { "ID": "A12",  "Rent": "$150.00" }
      }
    Keys not provided fall back to template defaults.
    """
    template_name: str = Field(..., examples=["wa_storage_lease"])
    template_parameters: dict[str, Any] = Field(default_factory=dict)
    signer_email: Optional[str] = Field(None, examples=["tenant@example.com"])
    completion_emails: Optional[list[str]] = Field(
        default_factory=list,
        examples=[["landlord@example.com", "agent@example.com"]],
    )

class DocumentSignRequest(BaseModel):
    signature_data: str  # data:image/png;base64,<b64>

# ── Outbound (service → n8n / client) ───────────────────────────────────────

class DocumentCreateResponse(BaseModel):
    id: str
    signing_url: str
    expires_at: datetime.datetime
    status: DocumentStatus

class DocumentStatusResponse(BaseModel):
    id: str
    status: DocumentStatus
    signed_pdf_url: Optional[str] = None

class DocumentMetadataResponse(BaseModel):
    id: str
    status: DocumentStatus
    template_name: Optional[str] = None
    signer_email: Optional[str] = None
    expires_at: datetime.datetime
    created_at: datetime.datetime
    pdf_url: str
    # List of {page, x0, y0, x1, y1} — positions of all Signature.Here fields
    signature_fields: list[dict] = Field(default_factory=list)
