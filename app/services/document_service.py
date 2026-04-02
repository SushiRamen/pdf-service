import os
import json
import asyncio
import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Document, DocumentStatus
from core.config import settings
from services.pdf_service import PDFService
from services.template_service import TemplateService


class DocumentService:

    @staticmethod
    async def create_from_template(
        db: AsyncSession,
        template_name: str,
        template_parameters: dict[str, Any],
        signer_email: Optional[str] = None,
        completion_emails: Optional[list[str]] = None,
        expires_in_days: int = 7,
    ) -> Document:
        """Create a document record by filling a stored PDF template."""
        # Create the DB record first to obtain a UUID
        doc = Document(
            original_pdf_path="",  # filled in below
            template_name=template_name,
            signer_email=signer_email,
            completion_emails=json.dumps(completion_emails or []),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=expires_in_days),
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Generate the filled PDF and detect signature field positions
        output_filename = f"{doc.id}_{template_name}.pdf"
        pdf_path, signature_fields = await TemplateService.generate_pdf(
            template_name=template_name,
            template_parameters=template_parameters,
            output_dir=settings.UPLOAD_DIR,
            output_filename=output_filename,
        )

        doc.original_pdf_path = pdf_path
        doc.signature_fields = json.dumps(signature_fields)
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def get_document(db: AsyncSession, doc_id: str) -> Document | None:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        return result.scalars().first()

    @staticmethod
    async def sign_document(db: AsyncSession, doc: Document, signature_data: str) -> Document:
        os.makedirs(settings.SIGNED_DIR, exist_ok=True)
        output_path = os.path.join(settings.SIGNED_DIR, f"signed_{doc.id}.pdf")

        # Load stored signature field positions (where Signature.Here was in the template)
        signature_fields = json.loads(doc.signature_fields or "[]")

        # PyMuPDF is blocking — run in a thread
        await asyncio.to_thread(
            PDFService.overlay_signature,
            doc.original_pdf_path,
            output_path,
            signature_data,
            signature_fields if signature_fields else None,
        )

        doc.signed_pdf_path = output_path
        doc.status = DocumentStatus.SIGNED
        await db.commit()
        await db.refresh(doc)
        return doc
