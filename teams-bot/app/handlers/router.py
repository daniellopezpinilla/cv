from __future__ import annotations

from typing import Any

from app.handlers.base import HandlerResult, MessageHandler
from app.models import IncomingMessage


# Re-export for convenience
__all__ = ["HandlerResult", "MessageHandler", "HandlerRouter"]


class HandlerRouter:
    """Encadena handlers. El primero que can_handle gana."""

    def __init__(self, handlers: list[MessageHandler]) -> None:
        self._handlers = handlers

    async def dispatch(self, message: IncomingMessage) -> HandlerResult:
        for handler in self._handlers:
            if handler.can_handle(message):  # type: ignore[arg-type]
                return await handler.handle(message)  # type: ignore[arg-type]
    async def dispatch(self, activity: dict[str, Any]) -> HandlerResult:
        for handler in self._handlers:
            if handler.can_handle(activity):
                return await handler.handle(activity)
        return HandlerResult(handled=False, detail="ningún handler aplicó")
