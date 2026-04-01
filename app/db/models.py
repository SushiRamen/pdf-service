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
    original_pdf_path = Column(String, nullable=False)
    signed_pdf_path = Column(String, nullable=True)
    signer_email = Column(String, nullable=True)
    # Stored as JSON string: '["email1@example.com", "email2@example.com"]'
    completion_emails = Column(Text, nullable=True)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
