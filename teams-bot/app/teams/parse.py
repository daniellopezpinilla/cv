from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.models import IncomingMessage
from app.state import parse_graph_datetime

_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(value: str) -> str:
    text = _HTML_TAG.sub(" ", value or "")
    return _WS.sub(" ", text).strip()


def is_user_chat_message(raw: dict[str, Any]) -> bool:
    """Ignora eventos de sistema de Teams (no son mensajes de usuario)."""
    msg_type = raw.get("messageType")
    if msg_type and msg_type != "message":
        return False
    return True


def graph_message_to_incoming(raw: dict[str, Any], chat_id: str = "") -> IncomingMessage:
    body = raw.get("body") or {}
    content = body.get("content") or ""
    text = (
        strip_html(content)
        if (body.get("contentType") or "").lower() == "html"
        else (content or "").strip()
    )

    from_block = raw.get("from") or {}
    user = from_block.get("user") or {}
    app = from_block.get("application") or {}

    from_id = str(user.get("id") or app.get("id") or "")
    from_name = str(user.get("displayName") or app.get("displayName") or "")
    is_from_app = bool(app) and not user

    created_raw = raw.get("createdDateTime")
    created_at: datetime | None = parse_graph_datetime(created_raw)

    return IncomingMessage(
        id=str(raw.get("id") or ""),
        text=text,
        from_id=from_id,
        from_name=from_name,
        created_at=created_at,
        is_from_app=is_from_app,
        chat_id=chat_id,
        raw=raw,
    )
