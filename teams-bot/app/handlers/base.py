from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models import IncomingMessage


@dataclass(frozen=True)
class HandlerResult:
    handled: bool
    detail: str = ""


class MessageHandler(ABC):
    """Extiende esta clase para agregar funciones nuevas al bot."""

    name: str = "base"

    @abstractmethod
    def can_handle(self, message: IncomingMessage) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def handle(self, message: IncomingMessage) -> HandlerResult:
        raise NotImplementedError
