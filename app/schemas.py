from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models import PermitStatus


class PermitTypeCreate(BaseModel):
    permit_type: str
    owner_email: str
    coordinator_email: str
    approver_email: str


class PermitRequestCreate(BaseModel):
    requester_name: str
    requester_email: str
    project_name: str
    project_location: str
    permit_types: list[PermitTypeCreate]


class PermitOut(BaseModel):
    id: int
    permit_type: str
    status: PermitStatus
    validation_errors: str | None = None
    sharepoint_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PermitRequestOut(BaseModel):
    id: int
    requester_name: str
    requester_email: str
    project_name: str
    project_location: str
    created_at: datetime
    permits: list[PermitOut]

    model_config = {"from_attributes": True}


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]
