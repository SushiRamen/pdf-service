import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.schemas import DocumentMetadataResponse
from db.models import DocumentStatus
from services.document_service import DocumentService
from core.config import settings
from core.limiter import limiter

router = APIRouter()


def _check_document_accessible(doc):
    """Raise if document doesn't exist or is in a non-accessible state."""
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/document/{token}", response_model=DocumentMetadataResponse)
@limiter.limit("60/minute")
async def get_document_metadata(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    """
    Returns document metadata for a given token.
    Used by the signing page to retrieve doc info and construct the PDF URL.
    Publicly accessible — no API key required.
    """
    doc = await DocumentService.get_document(db, token)
    _check_document_accessible(doc)

    pdf_url = f"{settings.BASE_URL}/api/v1/document/{token}/pdf"

    return DocumentMetadataResponse(
        id=doc.id,
        status=doc.status,
        signer_email=doc.signer_email,
        expires_at=doc.expires_at,
        created_at=doc.created_at,
        pdf_url=pdf_url,
    )


@router.get("/document/{token}/pdf")
@limiter.limit("60/minute")
async def get_document_pdf(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    """
    Streams the original unsigned PDF for a given token.
    This URL is passed to pdf.js on the signing page so the client can view the document.
    Publicly accessible — no API key required.
    """
    doc = await DocumentService.get_document(db, token)
    _check_document_accessible(doc)

    if not doc.original_pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")

    if doc.status == DocumentStatus.EXPIRED:
        raise HTTPException(status_code=410, detail="This document link has expired")

    return FileResponse(
        path=doc.original_pdf_path,
        media_type="application/pdf",
        filename=f"document_{doc.id}.pdf",
        headers={"Content-Disposition": "inline"},  # inline so pdf.js can load it in-browser
    )
