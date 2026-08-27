from __future__ import annotations

import base64
import time
from typing import Any
from urllib.parse import quote

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
    """Cliente Microsoft Graph para DMs de soporte, chat único o canal."""

    def __init__(
        self,
        *,
        app_id: str,
        app_password: str,
        tenant_id: str,
        support_user_id: str = "",
        chat_id: str = "",
        team_id: str = "",
        channel_id: str = "",
    ) -> None:
        self._app_id = app_id
        self._app_password = app_password
        self._tenant_id = tenant_id
        self._support_user_id = support_user_id
        self._chat_id = chat_id
        self._team_id = team_id
        self._channel_id = channel_id

    @property
    def mode(self) -> str:
        if self._support_user_id:
            return "support_dms"
        if self._chat_id:
            return "chat"
        return "channel"

    async def _token(self) -> str:
        return await get_graph_token(self._app_id, self._app_password, self._tenant_id)

    async def list_support_one_on_one_chats(self) -> list[dict[str, Any]]:
        """Lista chats 1:1 de la cuenta de soporte (cada usuario = un chat)."""
        if not self._support_user_id:
            raise RuntimeError("SUPPORT_USER_ID no configurado")

        user_seg = quote(self._support_user_id, safe="@")
        token = await self._token()
        chats: list[dict[str, Any]] = []

        # Primero intentar con filtro; si el tenant no lo soporta, listar y filtrar en cliente
        urls = [
            f"https://graph.microsoft.com/v1.0/users/{user_seg}/chats"
            f"?$top=50&$filter=chatType eq 'oneOnOne'",
            f"https://graph.microsoft.com/v1.0/users/{user_seg}/chats?$top=50",
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            for start_url in urls:
                url: str | None = start_url
                batch_ok = True
                temp: list[dict[str, Any]] = []
                while url:
                    response = await client.get(url, headers=_auth_headers(token))
                    if response.status_code == 400 and "$filter" in start_url:
                        batch_ok = False
                        break
                    response.raise_for_status()
                    data = response.json()
                    temp.extend(list(data.get("value") or []))
                    url = data.get("@odata.nextLink")
                if not batch_ok:
                    continue
                chats = temp
                break

        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for chat in chats:
            if (chat.get("chatType") or "") != "oneOnOne":
                continue
            cid = str(chat.get("id") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            unique.append(chat)
        return unique

    async def resolve_user_object_id(self, user_id_or_upn: str) -> str:
        token = await self._token()
        user_seg = quote(user_id_or_upn, safe="@")
        url = f"https://graph.microsoft.com/v1.0/users/{user_seg}?$select=id,userPrincipalName,displayName"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_auth_headers(token))
            response.raise_for_status()
            data = response.json()
        return str(data.get("id") or "")

    async def list_chat_messages(self, chat_id: str, top: int = 20) -> list[dict[str, Any]]:
        token = await self._token()
        chat_seg = quote(chat_id, safe="")
        url = f"https://graph.microsoft.com/v1.0/chats/{chat_seg}/messages?$top={top}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=_auth_headers(token))
            response.raise_for_status()
            data = response.json()
        return list(data.get("value") or [])

    async def list_recent_messages(self, top: int = 25) -> list[dict[str, Any]]:
        """Modo legacy: un chat o un canal fijo."""
        token = await self._token()
        if self._chat_id:
            url = f"https://graph.microsoft.com/v1.0/chats/{quote(self._chat_id, safe='')}/messages?$top={top}"
        else:
            url = (
                "https://graph.microsoft.com/v1.0/teams/"
                f"{quote(self._team_id, safe='')}/channels/{quote(self._channel_id, safe='')}"
                f"/messages?$top={top}"
            )
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
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        token = await self._token()
        target_chat = chat_id or self._chat_id
        if target_chat:
            url = f"https://graph.microsoft.com/v1.0/chats/{quote(target_chat, safe='')}/messages"
        else:
            url = (
                "https://graph.microsoft.com/v1.0/teams/"
                f"{quote(self._team_id, safe='')}/channels/{quote(self._channel_id, safe='')}/messages"
            )

        encoded = base64.b64encode(pdf_bytes).decode("ascii")
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
            response = await client.post(url, headers=_auth_headers(token), json=payload)
            if response.is_success:
                return response.json()

            fallback = {
                "body": {
                    "contentType": "html",
                    "content": html.replace('<attachment id="1"></attachment>', "")
                    + "<br/><i>(No se pudo adjuntar el PDF automáticamente; "
                    "solicita la guía a soporte.)</i>",
                }
            }
            retry = await client.post(url, headers=_auth_headers(token), json=fallback)
            retry.raise_for_status()
            return retry.json()
