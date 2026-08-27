from __future__ import annotations

import base64
import logging
import time
from typing import Any
from urllib.parse import quote

import httpx

from app.state import parse_graph_datetime

logger = logging.getLogger("teams-bot.graph")

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


def _chat_activity_datetime(chat: dict[str, Any]):
    preview = chat.get("lastMessagePreview") or {}
    for candidate in (
        chat.get("lastUpdatedDateTime"),
        preview.get("createdDateTime"),
    ):
        dt = parse_graph_datetime(candidate)
        if dt:
            return dt
    return None


def _sort_chats_by_recent(chats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        chats,
        key=lambda c: (_chat_activity_datetime(c) or parse_graph_datetime("1970-01-01T00:00:00Z")),
        reverse=True,
    )


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
        self._support_object_id: str | None = None

    @property
    def mode(self) -> str:
        if self._support_user_id:
            return "support_dms"
        if self._chat_id:
            return "chat"
        return "channel"

    async def _token(self) -> str:
        return await get_graph_token(self._app_id, self._app_password, self._tenant_id)

    async def list_support_one_on_one_chats(
        self,
        *,
        max_pages: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista chats 1:1 recientes de la cuenta de soporte (paginación limitada)."""
        if not self._support_user_id:
            raise RuntimeError("SUPPORT_USER_ID no configurado")

        user_seg = quote(self._support_user_id, safe="@")
        token = await self._token()
        chats: list[dict[str, Any]] = []

        base = f"https://graph.microsoft.com/v1.0/users/{user_seg}/chats"
        # Orden soportado por Graph: lastMessagePreview/createdDateTime
        start_urls = [
            f"{base}?$top={page_size}&$filter=chatType eq 'oneOnOne'"
            f"&$orderby=lastMessagePreview/createdDateTime desc",
            f"{base}?$top={page_size}&$filter=chatType eq 'oneOnOne'",
            f"{base}?$top={page_size}",
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            for start_url in start_urls:
                url: str | None = start_url
                temp: list[dict[str, Any]] = []
                pages = 0
                ok = True
                while url and pages < max_pages:
                    response = await client.get(url, headers=_auth_headers(token))
                    if response.status_code == 400 and pages == 0:
                        ok = False
                        break
                    response.raise_for_status()
                    data = response.json()
                    temp.extend(list(data.get("value") or []))
                    url = data.get("@odata.nextLink")
                    pages += 1
                if ok and temp:
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

        return _sort_chats_by_recent(unique)

    async def resolve_user_object_id(self, user_id_or_upn: str) -> str:
        if self._support_object_id:
            return self._support_object_id

        token = await self._token()
        user_seg = quote(user_id_or_upn, safe="@")
        url = f"https://graph.microsoft.com/v1.0/users/{user_seg}?$select=id,userPrincipalName,displayName"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=_auth_headers(token))
            response.raise_for_status()
            data = response.json()
        self._support_object_id = str(data.get("id") or "")
        return self._support_object_id

    async def list_chat_messages(self, chat_id: str, top: int = 20) -> list[dict[str, Any]]:
        token = await self._token()
        chat_seg = quote(chat_id, safe="")
        url = (
            f"https://graph.microsoft.com/v1.0/chats/{chat_seg}/messages"
            f"?$top={top}&$orderby=createdDateTime desc"
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=_auth_headers(token))
            if response.status_code == 400:
                url = f"https://graph.microsoft.com/v1.0/chats/{chat_seg}/messages?$top={top}"
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
        if not target_chat:
            url = (
                "https://graph.microsoft.com/v1.0/teams/"
                f"{quote(self._team_id, safe='')}/channels/{quote(self._channel_id, safe='')}/messages"
            )
            return await self._post_message(token, url, self._pdf_payload(text, pdf_bytes, pdf_filename))

        chat_seg = quote(target_chat, safe="")
        urls = [f"https://graph.microsoft.com/v1.0/chats/{chat_seg}/messages"]
        if self._support_user_id:
            user_seg = quote(self._support_user_id, safe="@")
            urls.append(
                f"https://graph.microsoft.com/v1.0/users/{user_seg}/chats/{chat_seg}/messages"
            )

        last_error = ""
        async with httpx.AsyncClient(timeout=120.0) as client:
            for url in urls:
                # 1) Texto simple (diagnóstico + fallback útil)
                plain = {"body": {"contentType": "text", "content": text}}
                response = await client.post(url, headers=_auth_headers(token), json=plain)
                if response.is_success:
                    logger.info("Mensaje de texto enviado al chat %s", target_chat[:24])
                    # 2) Intentar PDF en mensaje aparte (algunos tenants bloquean hostedContents)
                    pdf_payload = self._pdf_payload(text, pdf_bytes, pdf_filename)
                    pdf_resp = await client.post(url, headers=_auth_headers(token), json=pdf_payload)
                    if pdf_resp.is_success:
                        logger.info("PDF enviado al chat %s", target_chat[:24])
                    else:
                        logger.warning(
                            "Texto OK pero PDF falló chat=%s status=%s body=%s",
                            target_chat[:24],
                            pdf_resp.status_code,
                            pdf_resp.text[:400],
                        )
                    return response.json()

                last_error = response.text[:500]
                logger.warning(
                    "Fallo envío texto chat=%s url=%s status=%s body=%s",
                    target_chat[:24],
                    url.split("/v1.0/")[-1][:60],
                    response.status_code,
                    last_error,
                )
                if response.status_code == 403:
                    logger.error(
                        "403 al enviar: confirma Chat.ReadWrite.All (Aplicación + admin consent) "
                        "y política Teams CsApplicationAccessPolicy para la App ID."
                    )

        raise RuntimeError(
            f"No se pudo enviar mensaje al chat {target_chat[:24]}. "
            f"Último error: {last_error}"
        )

    @staticmethod
    def _pdf_payload(text: str, pdf_bytes: bytes, pdf_filename: str) -> dict[str, Any]:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        html = text.replace("\n", "<br/>") + '<br/><attachment id="1"></attachment>'
        return {
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

    async def _post_message(
        self, token: str, url: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=_auth_headers(token), json=payload)
            response.raise_for_status()
            return response.json()
