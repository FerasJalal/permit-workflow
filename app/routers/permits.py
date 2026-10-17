import logging
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import Permit, PermitRequest, PermitStatus
from app.schemas import PermitRequestCreate, PermitRequestOut, PermitOut, ValidationResult
from app.services import workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permits", tags=["permits"])


@router.post("", response_model=PermitRequestOut, status_code=201)
async def create_permit_request(
    body: PermitRequestCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    request = PermitRequest(
        requester_name=body.requester_name,
        requester_email=body.requester_email,
        project_name=body.project_name,
        project_location=body.project_location,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    permit_dicts = [pt.model_dump() for pt in body.permit_types]
    permits = await workflow.create_permits(db, request, permit_dicts)

    for permit in permits:
        background_tasks.add_task(workflow.fill_and_send_template, permit.id, request.id)

    await db.refresh(request, attribute_names=["permits"])
    return request


@router.get("/{request_id}", response_model=PermitRequestOut)
async def get_permit_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PermitRequest)
        .options(selectinload(PermitRequest.permits))
        .where(PermitRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(404, "Permit request not found")
    return request


@router.get("/{request_id}/permits/{permit_id}", response_model=PermitOut)
async def get_permit(
    request_id: int,
    permit_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Permit).where(Permit.id == permit_id, Permit.request_id == request_id)
    )
    permit = result.scalar_one_or_none()
    if not permit:
        raise HTTPException(404, "Permit not found")
    return permit


@router.post("/{permit_id}/upload", response_model=ValidationResult)
async def upload_completed_excel(
    permit_id: int,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Permit).where(Permit.id == permit_id))
    permit = result.scalar_one_or_none()
    if not permit:
        raise HTTPException(404, "Permit not found")

    if permit.status not in (
        PermitStatus.TEMPLATE_SENT,
        PermitStatus.VALIDATION_FAILED,
    ):
        raise HTTPException(400, f"Cannot upload in current status: {permit.status}")

    upload_dir = settings.uploads_path / str(permit_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"uploaded_{file.filename}"

    async with aiofiles.open(upload_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    validation = await workflow.process_upload(db, permit, upload_path)
    return validation


@router.get("", response_model=list[PermitRequestOut])
async def list_permit_requests(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PermitRequest)
        .options(selectinload(PermitRequest.permits))
        .offset(skip)
        .limit(limit)
        .order_by(PermitRequest.created_at.desc())
    )
    return result.scalars().all()
