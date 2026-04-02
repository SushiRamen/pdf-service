import uuid
import datetime
from sqlalchemy import Column, String, Enum, DateTime, Text
from db.database import Base
import enum


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    SIGNED = "signed"
    EXPIRED = "expired"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_name = Column(String, nullable=True)          # e.g. "wa_storage_lease"
    original_pdf_path = Column(String, nullable=False)
    signed_pdf_path = Column(String, nullable=True)
    signer_email = Column(String, nullable=True)
    # JSON string: '["email1@example.com"]'
    completion_emails = Column(Text, nullable=True)
    # JSON array of {page, x0, y0, x1, y1} dicts — detected from Signature.Here in the template
    signature_fields = Column(Text, nullable=True)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
