from pydantic import BaseModel
from db.models import DocumentStatus
import datetime
from typing import List, Optional

class DocumentCreateResponse(BaseModel):
    id: str
    signing_url: str
    expires_at: datetime.datetime
    status: DocumentStatus

class DocumentSignRequest(BaseModel):
    signature_data: str  # Base64 encoded PNG data URL (data:image/png;base64,...)

class DocumentStatusResponse(BaseModel):
    id: str
    status: DocumentStatus
    signed_pdf_url: Optional[str] = None

class DocumentMetadataResponse(BaseModel):
    id: str
    status: DocumentStatus
    signer_email: Optional[str] = None
    expires_at: datetime.datetime
    created_at: datetime.datetime
    pdf_url: str  # URL client can use to fetch the PDF for pdf.js
