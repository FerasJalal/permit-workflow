import base64
import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


async def _get_access_token() -> str:
    url = TOKEN_URL.format(tenant=settings.graph_tenant_id)
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data={
            "client_id": settings.graph_client_id,
            "client_secret": settings.graph_client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


async def send_permit_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    attachment_path: Path | None = None,
):
    token = await _get_access_token()
    url = SEND_MAIL_URL.format(sender=settings.graph_sender_email)

    message: dict = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "toRecipients": [{"emailAddress": {"address": to_email, "name": to_name}}],
    }

    if attachment_path and attachment_path.exists():
        file_bytes = attachment_path.read_bytes()
        message["attachments"] = [{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": attachment_path.name,
            "contentBytes": base64.b64encode(file_bytes).decode(),
        }]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json={"message": message, "saveToSentItems": True},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()

    logger.info("Email sent to %s", to_email)
