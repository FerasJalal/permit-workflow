import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


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


async def upload_to_sharepoint(file_path: Path, filename: str) -> str:
    token = await _get_access_token()

    folder = settings.sharepoint_folder_path.strip("/")
    url = (
        f"https://graph.microsoft.com/v1.0/sites/{settings.sharepoint_site_id}"
        f"/drives/{settings.sharepoint_drive_id}"
        f"/root:/{folder}/{filename}:/content"
    )

    file_bytes = file_path.read_bytes()

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            url,
            content=file_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/pdf",
            },
        )
        resp.raise_for_status()

    web_url = resp.json().get("webUrl", "")
    logger.info("Uploaded %s to SharePoint: %s", filename, web_url)
    return web_url
