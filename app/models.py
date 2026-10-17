import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class PermitStatus(str, enum.Enum):
    DRAFT = "draft"
    TEMPLATE_SENT = "template_sent"
    UPLOADED = "uploaded"
    VALIDATION_FAILED = "validation_failed"
    PDF_GENERATED = "pdf_generated"
    SENT_FOR_SIGNING = "sent_for_signing"
    SIGNED = "signed"
    COMPLETED = "completed"
    FAILED = "failed"


class PermitRequest(Base):
    __tablename__ = "permit_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String, nullable=False)
    requester_email = Column(String, nullable=False)
    project_name = Column(String, nullable=False)
    project_location = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    permits = relationship("Permit", back_populates="request")


class Permit(Base):
    __tablename__ = "permits"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("permit_requests.id"), nullable=False)
    permit_type = Column(String, nullable=False)
    status = Column(Enum(PermitStatus), default=PermitStatus.DRAFT)

    template_file = Column(String, nullable=True)
    uploaded_file = Column(String, nullable=True)
    pdf_file = Column(String, nullable=True)
    signed_pdf_file = Column(String, nullable=True)

    adobe_agreement_id = Column(String, nullable=True)
    sharepoint_url = Column(String, nullable=True)

    validation_errors = Column(Text, nullable=True)

    owner_email = Column(String, nullable=True)
    coordinator_email = Column(String, nullable=True)
    approver_email = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    request = relationship("PermitRequest", back_populates="permits")
