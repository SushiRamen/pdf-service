import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.schemas import DocumentStatusResponse, DocumentSignRequest
from db.models import DocumentStatus
from services.document_service import DocumentService
from core.limiter import limiter

router = APIRouter()
# Absolute path: app/api/endpoints/ -> up 2 levels -> app/ -> templates/
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/{token}", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def sign_page(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    doc = await DocumentService.get_document(db, token)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == DocumentStatus.SIGNED:
        return templates.TemplateResponse("success.html", {"request": request, "doc_id": doc.id})

    if datetime.datetime.utcnow() > doc.expires_at:
        doc.status = DocumentStatus.EXPIRED
        await db.commit()
        return templates.TemplateResponse("expired.html", {"request": request})

    return templates.TemplateResponse("sign.html", {"request": request, "doc_id": doc.id})


@router.post("/{token}/submit", response_model=DocumentStatusResponse)
@limiter.limit("5/minute")
async def submit_signature(
    request: Request, token: str, data: DocumentSignRequest, db: AsyncSession = Depends(get_db)
):
    doc = await DocumentService.get_document(db, token)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != DocumentStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Document is already {doc.status.value}")
    if datetime.datetime.utcnow() > doc.expires_at:
        raise HTTPException(status_code=400, detail="Document has expired")

    signed_doc = await DocumentService.sign_document(db, doc, data.signature_data)

    # TODO: Send signed PDF to completion_emails via email service (see README TODO)
    # TODO: POST webhook to n8n on completion (see README TODO)

    return DocumentStatusResponse(
        id=signed_doc.id,
        status=signed_doc.status,
        signed_pdf_url=f"/sign/download/{signed_doc.id}",
    )


@router.get("/download/{token}", response_class=FileResponse)
@limiter.limit("10/minute")
async def download_signed(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    doc = await DocumentService.get_document(db, token)
    if not doc or not doc.signed_pdf_path:
        raise HTTPException(status_code=404, detail="Signed document not found")
    return FileResponse(
        path=doc.signed_pdf_path,
        filename=f"signed_{doc.id}.pdf",
        media_type="application/pdf",
    )
