from __future__ import annotations

from app.config import Settings
from app.handlers.base import HandlerResult, MessageHandler
from app.models import IncomingMessage
from app.schedule import is_off_hours
from app.teams.graph import GraphTeamsClient
from typing import Any

from app.config import Settings
from app.handlers.base import HandlerResult, MessageHandler
from app.schedule import is_off_hours
from app.teams.reply import send_pdf_reply


def _is_user_message(activity: dict[str, Any]) -> bool:
    if activity.get("type") != "message":
        return False
    # Ignorar mensajes generados por el propio bot
    recipient = activity.get("recipient") or {}
    from_user = activity.get("from") or {}
    if from_user.get("id") and recipient.get("id") and from_user.get("id") == recipient.get("id"):
        return False
    text = (activity.get("text") or "").strip()
    has_attachments = bool(activity.get("attachments"))
    return bool(text or has_attachments)


class OffHoursGuideHandler(MessageHandler):
    """v1: fuera de horario → texto + PDF para crear un caso."""

    name = "offhours_guide"

    def __init__(self, settings: Settings, graph: GraphTeamsClient) -> None:
        self._settings = settings
        self._graph = graph

    def can_handle(self, message: IncomingMessage) -> bool:  # type: ignore[override]
        if message.is_from_app:
            return False
        if not (message.text or message.raw.get("attachments")):
            return False
        return is_off_hours(timezone=self._settings.timezone)

    async def handle(self, message: IncomingMessage) -> HandlerResult:  # type: ignore[override]
        pdf_bytes = self._settings.pdf_path.read_bytes()
        await self._graph.send_text_with_pdf(
            text=self._settings.reply_text,
            pdf_bytes=pdf_bytes,
            pdf_filename=self._settings.pdf_filename,
        )
        return HandlerResult(
            handled=True,
            detail=f"guía enviada (respuesta a {message.id})",
        )
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def can_handle(self, activity: dict[str, Any]) -> bool:
        if not _is_user_message(activity):
            return False
        return is_off_hours(timezone=self._settings.timezone)

    async def handle(self, activity: dict[str, Any]) -> HandlerResult:
        await send_pdf_reply(
            activity=activity,
            text=self._settings.reply_text,
            pdf_path=self._settings.pdf_path,
            pdf_filename=self._settings.pdf_filename,
            app_id=self._settings.app_id,
            app_password=self._settings.app_password,
            tenant_id=self._settings.tenant_id or None,
        )
        return HandlerResult(handled=True, detail="guía fuera de horario enviada")
