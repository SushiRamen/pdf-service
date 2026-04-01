import json
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from core.security import get_api_key
from db.database import get_db
from db.schemas import DocumentCreateResponse
from services.document_service import DocumentService
from core.config import settings
from core.limiter import limiter
from typing import Optional

router = APIRouter()


@router.post("/documents/create", response_model=DocumentCreateResponse, dependencies=[Depends(get_api_key)])
@limiter.limit("10/minute")
async def create_document(
    request: Request,
    file: UploadFile = File(..., description="PDF file to be signed"),
    signer_email: Optional[str] = Form(None, description="Email address of the signer"),
    completion_emails: Optional[str] = Form(
        None,
        description='JSON array string of emails to receive the signed PDF. e.g. ["a@b.com","c@d.com"]',
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new document signing session.

    Send as multipart/form-data:
    - file: the PDF (binary)
    - signer_email: recipient who signs
    - completion_emails: JSON array string of addresses to receive the signed copy
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # Parse completion_emails from JSON string
    emails_list: list[str] = []
    if completion_emails:
        try:
            parsed = json.loads(completion_emails)
            if not isinstance(parsed, list):
                raise ValueError("Must be a JSON array")
            emails_list = [str(e) for e in parsed]
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail='completion_emails must be a valid JSON array string, e.g. ["a@b.com"]',
            )

    doc = await DocumentService.create_document(
        db,
        file,
        signer_email=signer_email,
        completion_emails=emails_list,
    )

    signing_url = f"{settings.BASE_URL}/sign/{doc.id}"
    return DocumentCreateResponse(
        id=doc.id,
        signing_url=signing_url,
        expires_at=doc.expires_at,
        status=doc.status,
    )
