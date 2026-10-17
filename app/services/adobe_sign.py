import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.adobe_sign_access_token}",
        "Content-Type": "application/json",
    }


async def upload_transient_document(pdf_path: Path) -> str:
    url = f"{settings.adobe_sign_base_url}/transientDocuments"

    async with httpx.AsyncClient() as client:
        with open(pdf_path, "rb") as f:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.adobe_sign_access_token}"},
                files={"File": (pdf_path.name, f, "application/pdf")},
            )
        resp.raise_for_status()

    transient_id = resp.json()["transientDocumentId"]
    logger.info("Uploaded transient document: %s", transient_id)
    return transient_id


async def create_agreement(
    transient_document_id: str,
    agreement_name: str,
    signer_emails: list[dict],
) -> str:
    url = f"{settings.adobe_sign_base_url}/agreements"

    participant_sets = []
    for i, signer in enumerate(signer_emails, start=1):
        participant_sets.append({
            "memberInfos": [{"email": signer["email"]}],
            "order": i,
            "role": signer.get("role", "SIGNER"),
        })

    payload = {
        "fileInfos": [{"transientDocumentId": transient_document_id}],
        "name": agreement_name,
        "participantSetsInfo": participant_sets,
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()

    agreement_id = resp.json()["id"]
    logger.info("Created agreement: %s", agreement_id)
    return agreement_id


async def register_webhook(agreement_id: str) -> str:
    url = f"{settings.adobe_sign_base_url}/webhooks"

    payload = {
        "name": f"permit-webhook-{agreement_id}",
        "scope": "RESOURCE",
        "resourceType": "AGREEMENT",
        "resourceId": agreement_id,
        "state": "ACTIVE",
        "webhookSubscriptionEvents": [
            "AGREEMENT_ALL",
        ],
        "webhookUrlInfo": {"url": settings.adobe_sign_webhook_url},
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()

    webhook_id = resp.json()["id"]
    logger.info("Registered webhook %s for agreement %s", webhook_id, agreement_id)
    return webhook_id


async def download_signed_document(agreement_id: str, output_path: Path) -> Path:
    url = f"{settings.adobe_sign_base_url}/agreements/{agreement_id}/combinedDocument"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {settings.adobe_sign_access_token}"},
        )
        resp.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)
    logger.info("Downloaded signed PDF to %s", output_path)
    return output_path
