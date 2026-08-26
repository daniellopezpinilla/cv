from __future__ import annotations

import base64
import time
from typing import Any

import httpx

_SCOPE = "https://graph.microsoft.com/.default"

_cached_token: str | None = None
_cached_expires_at: float = 0.0


async def get_graph_token(app_id: str, app_password: str, tenant_id: str) -> str:
    global _cached_token, _cached_expires_at

    now = time.time()
    if _cached_token and now < _cached_expires_at - 60:
        return _cached_token

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": app_id,
        "client_secret": app_password,
        "scope": _SCOPE,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, data=data)
        response.raise_for_status()
        payload = response.json()

    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"No se obtuvo access_token de Graph: {payload}")

    _cached_token = token
    _cached_expires_at = now + int(payload.get("expires_in", 3600))
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


class GraphTeamsClient:
    """Cliente mínimo de Microsoft Graph para chat/canal de Teams."""

    def __init__(
        self,
        *,
        app_id: str,
        app_password: str,
        tenant_id: str,
        chat_id: str = "",
        team_id: str = "",
        channel_id: str = "",
    ) -> None:
        self._app_id = app_id
        self._app_password = app_password
        self._tenant_id = tenant_id
        self._chat_id = chat_id
        self._team_id = team_id
        self._channel_id = channel_id

    @property
    def mode(self) -> str:
        if self._chat_id:
            return "chat"
        return "channel"

    def _messages_url(self) -> str:
        if self._chat_id:
            return f"https://graph.microsoft.com/v1.0/chats/{self._chat_id}/messages"
        return (
            "https://graph.microsoft.com/v1.0/teams/"
            f"{self._team_id}/channels/{self._channel_id}/messages"
        )

    async def list_recent_messages(self, top: int = 25) -> list[dict[str, Any]]:
        token = await get_graph_token(self._app_id, self._app_password, self._tenant_id)
        url = f"{self._messages_url()}?$top={top}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=_auth_headers(token))
            response.raise_for_status()
            data = response.json()
        return list(data.get("value") or [])

    async def send_text_with_pdf(
        self,
        *,
        text: str,
        pdf_bytes: bytes,
        pdf_filename: str,
    ) -> dict[str, Any]:
        token = await get_graph_token(self._app_id, self._app_password, self._tenant_id)

        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        # Attachment reference + hosted content (Graph)
        html = text.replace("\n", "<br/>") + '<br/><attachment id="1"></attachment>'
        payload: dict[str, Any] = {
            "body": {"contentType": "html", "content": html},
            "attachments": [
                {
                    "id": "1",
                    "contentType": "reference",
                    "contentUrl": None,
                    "name": pdf_filename,
                }
            ],
            "hostedContents": [
                {
                    "@microsoft.graph.temporaryId": "1",
                    "contentBytes": encoded,
                    "contentType": "application/pdf",
                }
            ],
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self._messages_url(),
                headers=_auth_headers(token),
                json=payload,
            )
            if response.is_success:
                return response.json()

            # Fallback: mensaje sin adjunto si el tenant bloquea hostedContents
            fallback = {
                "body": {
                    "contentType": "html",
                    "content": html.replace('<attachment id="1"></attachment>', "")
                    + "<br/><i>(No se pudo adjuntar el PDF automáticamente; "
                    "solicita la guía a soporte.)</i>",
                }
            }
            retry = await client.post(
                self._messages_url(),
                headers=_auth_headers(token),
                json=fallback,
            )
            retry.raise_for_status()
            return retry.json()
