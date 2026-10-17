import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Permit, PermitRequest, PermitStatus
from app.services import (
    template_filler,
    validator,
    pdf_converter,
    graph_mail,
    adobe_sign,
    sharepoint,
)

logger = logging.getLogger(__name__)


async def create_permits(db: AsyncSession, request: PermitRequest, permit_types: list[dict]) -> list[Permit]:
    permits = []
    for pt in permit_types:
        permit = Permit(
            request_id=request.id,
            permit_type=pt["permit_type"],
            owner_email=pt["owner_email"],
            coordinator_email=pt["coordinator_email"],
            approver_email=pt["approver_email"],
        )
        db.add(permit)
        permits.append(permit)

    await db.commit()
    for p in permits:
        await db.refresh(p)

    return permits


async def fill_and_send_template(db: AsyncSession, permit: Permit, request: PermitRequest):
    data = {
        "permit_id": permit.id,
        "requester_name": request.requester_name,
        "requester_email": request.requester_email,
        "project_name": request.project_name,
        "project_location": request.project_location,
        "permit_type": permit.permit_type,
    }

    filled_path = await template_filler.fill_template(permit.permit_type, data)
    permit.template_file = str(filled_path)

    upload_link = f"{settings.app_base_url}/permits/{permit.id}/upload"

    body = f"""
    <h2>Permit Application - {permit.permit_type}</h2>
    <p>Hello {request.requester_name},</p>
    <p>Please find the attached permit template for <strong>{permit.permit_type}</strong>.</p>
    <p>Fill in all required fields and upload the completed file here:</p>
    <p><a href="{upload_link}">{upload_link}</a></p>
    <p>Thank you.</p>
    """

    await graph_mail.send_permit_email(
        to_email=request.requester_email,
        to_name=request.requester_name,
        subject=f"Permit Template: {permit.permit_type} - {request.project_name}",
        body_html=body,
        attachment_path=filled_path,
    )

    permit.status = PermitStatus.TEMPLATE_SENT
    await db.commit()
    logger.info("Template sent for permit %d", permit.id)


async def process_upload(db: AsyncSession, permit: Permit, uploaded_path: Path):
    permit.uploaded_file = str(uploaded_path)
    permit.status = PermitStatus.UPLOADED
    await db.commit()

    result = await validator.validate_excel(uploaded_path)

    if not result.valid:
        permit.status = PermitStatus.VALIDATION_FAILED
        permit.validation_errors = "\n".join(result.errors)
        await db.commit()
        logger.warning("Validation failed for permit %d: %s", permit.id, result.errors)
        return result

    permit.validation_errors = None
    pdf_path = await pdf_converter.convert_excel_to_pdf(uploaded_path)
    permit.pdf_file = str(pdf_path)
    permit.status = PermitStatus.PDF_GENERATED
    await db.commit()

    await send_for_signing(db, permit)
    return result


async def send_for_signing(db: AsyncSession, permit: Permit):
    pdf_path = Path(permit.pdf_file)

    transient_id = await adobe_sign.upload_transient_document(pdf_path)

    signers = [
        {"email": permit.owner_email, "role": "SIGNER"},
        {"email": permit.coordinator_email, "role": "SIGNER"},
        {"email": permit.approver_email, "role": "APPROVER"},
    ]

    request = await db.get(PermitRequest, permit.request_id)
    agreement_name = f"Permit-{permit.permit_type}-{request.project_name}"

    agreement_id = await adobe_sign.create_agreement(transient_id, agreement_name, signers)
    permit.adobe_agreement_id = agreement_id
    permit.status = PermitStatus.SENT_FOR_SIGNING
    await db.commit()

    await adobe_sign.register_webhook(agreement_id)
    logger.info("Permit %d sent for signing, agreement %s", permit.id, agreement_id)


async def handle_signing_complete(db: AsyncSession, agreement_id: str):
    result = await db.execute(
        select(Permit).where(Permit.adobe_agreement_id == agreement_id)
    )
    permit = result.scalar_one_or_none()
    if not permit:
        logger.warning("No permit found for agreement %s", agreement_id)
        return

    permit.status = PermitStatus.SIGNED

    signed_path = settings.generated_path / f"signed_{permit.id}.pdf"
    await adobe_sign.download_signed_document(agreement_id, signed_path)
    permit.signed_pdf_file = str(signed_path)

    request = await db.get(PermitRequest, permit.request_id)
    filename = f"{request.project_name}_{permit.permit_type}_signed.pdf"
    sp_url = await sharepoint.upload_to_sharepoint(signed_path, filename)
    permit.sharepoint_url = sp_url

    permit.status = PermitStatus.COMPLETED
    await db.commit()

    await _notify_all_parties(permit, request, signed_path)
    logger.info("Permit %d completed", permit.id)


async def _notify_all_parties(permit: Permit, request: PermitRequest, signed_path: Path):
    recipients = [
        (request.requester_email, request.requester_name),
        (permit.owner_email, "Owner"),
        (permit.coordinator_email, "Coordinator"),
        (permit.approver_email, "Approver"),
    ]

    body = f"""
    <h2>Signed Permit - {permit.permit_type}</h2>
    <p>The permit for <strong>{request.project_name}</strong> has been fully signed.</p>
    <p>Please find the signed permit attached.</p>
    <p>SharePoint link: <a href="{permit.sharepoint_url}">{permit.sharepoint_url}</a></p>
    """

    for email, name in recipients:
        await graph_mail.send_permit_email(
            to_email=email,
            to_name=name,
            subject=f"Signed Permit: {permit.permit_type} - {request.project_name}",
            body_html=body,
            attachment_path=signed_path,
        )
