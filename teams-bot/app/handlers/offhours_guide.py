from __future__ import annotations

from app.config import Settings
from app.handlers.base import HandlerResult, MessageHandler
from app.models import IncomingMessage
from app.schedule import is_off_hours
from app.teams.graph import GraphTeamsClient


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
