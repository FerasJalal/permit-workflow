import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import workflow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/adobe-sign")
async def adobe_sign_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()

    event = body.get("event", "")
    agreement_id = body.get("agreement", {}).get("id") or body.get("agreementId")

    logger.info("Adobe Sign webhook event: %s for agreement %s", event, agreement_id)

    if event == "AGREEMENT_ACTION_COMPLETED" and agreement_id:
        status = body.get("agreement", {}).get("status", "")
        if status == "SIGNED":
            await workflow.handle_signing_complete(db, agreement_id)

    return {"status": "ok"}


@router.get("/adobe-sign")
async def adobe_sign_webhook_verification(request: Request):
    return Response(
        content="",
        headers={
            "X-AdobeSign-ClientId": request.headers.get("X-AdobeSign-ClientId", ""),
        },
    )
