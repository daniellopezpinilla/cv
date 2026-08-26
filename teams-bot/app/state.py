from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class PollState:
    last_message_id: str = ""
    last_created: str = ""  # ISO string from Graph createdDateTime
    bootstrapped: bool = False


def load_state(path: Path) -> PollState:
    if not path.is_file():
        return PollState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PollState()
    return PollState(
        last_message_id=str(data.get("last_message_id") or ""),
        last_created=str(data.get("last_created") or ""),
        bootstrapped=bool(data.get("bootstrapped")),
    )


def save_state(path: Path, state: PollState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "last_message_id": state.last_message_id,
                "last_created": state.last_created,
                "bootstrapped": state.bootstrapped,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_graph_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def is_newer_than_state(
    *,
    message_id: str,
    created: str | None,
    state: PollState,
) -> bool:
    """True si el mensaje es posterior al último procesado."""
    if not state.last_message_id and not state.last_created:
        return True
    created_dt = parse_graph_datetime(created)
    last_dt = parse_graph_datetime(state.last_created)
    if created_dt and last_dt:
        if created_dt > last_dt:
            return True
        if created_dt < last_dt:
            return False
        return message_id != state.last_message_id and message_id > state.last_message_id
    return message_id != state.last_message_id


def mark_bootstrapped_now(path: Path) -> PollState:
    """Marca bootstrap sin mensajes previos (evita tragarse el primer mensaje real)."""
    state = PollState(
        last_message_id="",
        last_created=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        bootstrapped=True,
    )
    save_state(path, state)
    return state
