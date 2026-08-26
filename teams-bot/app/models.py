from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class IncomingMessage:
    """Mensaje normalizado (independiente de webhook o poller)."""

    id: str
    text: str
    from_id: str
    from_name: str
    created_at: datetime | None
    is_from_app: bool
    raw: dict[str, Any] = field(repr=False, default_factory=dict)
