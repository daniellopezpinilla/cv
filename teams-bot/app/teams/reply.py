from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.teams.auth import get_bot_framework_token


def _build_attachment(pdf_path: Path, pdf_filename: str) -> dict[str, Any]:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")

    content = pdf_path.read_bytes()
    encoded = base64.b64encode(content).decode("ascii")
    return {
        "name": pdf_filename,
        "contentType": "application/pdf",
        "contentUrl": f"data:application/pdf;base64,{encoded}",
    }


async def send_pdf_reply(
    *,
    activity: dict[str, Any],
    text: str,
    pdf_path: Path,
    pdf_filename: str,
    app_id: str,
    app_password: str,
    tenant_id: str | None = None,
) -> None:
    service_url = (activity.get("serviceUrl") or "").rstrip("/")
    conversation = activity.get("conversation") or {}
    conversation_id = conversation.get("id")
    activity_id = activity.get("id")

    if not service_url or not conversation_id:
        raise ValueError("Activity sin serviceUrl o conversation.id")

    token = await get_bot_framework_token(app_id, app_password, tenant_id=tenant_id)
    attachment = _build_attachment(pdf_path, pdf_filename)

    reply: dict[str, Any] = {
        "type": "message",
        "text": text,
        "attachments": [attachment],
        "from": activity.get("recipient"),
        "recipient": activity.get("from"),
        "conversation": conversation,
        "replyToId": activity_id,
    }

    # Prefer reply-to activity URL when available
    conv_seg = quote(conversation_id, safe="")
    if activity_id:
        url = f"{service_url}/v3/conversations/{conv_seg}/activities/{quote(activity_id, safe='')}"
    else:
        url = f"{service_url}/v3/conversations/{conv_seg}/activities"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=reply, headers=headers)
        response.raise_for_status()
