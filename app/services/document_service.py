import os
import json
import asyncio
import aiofiles
import datetime
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Document, DocumentStatus
from core.config import settings
from services.pdf_service import PDFService


class DocumentService:
    @staticmethod
    async def create_document(
        db: AsyncSession,
        file: UploadFile,
        signer_email: Optional[str] = None,
        completion_emails: Optional[List[str]] = None,
        expires_in_days: int = 7,
    ) -> Document:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # Create DB record first to get the UUID (used in filename)
        doc = Document(
            # Placeholder — will be updated below once file is saved
            original_pdf_path="",
            signer_email=signer_email,
            completion_emails=json.dumps(completion_emails or []),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=expires_in_days),
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Save PDF to disk using the UUID as filename prefix
        safe_filename = os.path.basename(file.filename or "document.pdf")
        file_path = os.path.join(settings.UPLOAD_DIR, f"{doc.id}_{safe_filename}")
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)

        # Update record with final file path
        doc.original_pdf_path = file_path
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
        output_filename = f"signed_{doc.id}.pdf"
        output_path = os.path.join(settings.SIGNED_DIR, output_filename)

        # Run blocking PyMuPDF op in a thread to avoid blocking the event loop
        await asyncio.to_thread(
            PDFService.overlay_signature,
            doc.original_pdf_path,
            output_path,
            signature_data,
        )

        doc.signed_pdf_path = output_path
        doc.status = DocumentStatus.SIGNED
        await db.commit()
        await db.refresh(doc)
        return doc
