from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models import IncomingMessage
from typing import Any


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
    def can_handle(self, activity: dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def handle(self, activity: dict[str, Any]) -> HandlerResult:
        raise NotImplementedError
