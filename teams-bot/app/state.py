from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ChatCursor:
    last_message_id: str = ""
    last_created: str = ""
    bootstrapped: bool = False


@dataclass
class PollState:
    """Estado multi-chat (DMs) con compatibilidad al formato viejo de un solo chat."""

    chats: dict[str, ChatCursor] = field(default_factory=dict)
    # ISO UTC: solo se procesan mensajes posteriores a este instante (modo rápido)
    watching_since: str = ""
    # legacy single-chat fields
    last_message_id: str = ""
    last_created: str = ""
    bootstrapped: bool = False


def load_state(path: Path) -> PollState:
    if not path.is_file():
        return PollState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PollState()

    chats_raw = data.get("chats") or {}
    chats: dict[str, ChatCursor] = {}
    if isinstance(chats_raw, dict):
        for chat_id, cursor in chats_raw.items():
            if not isinstance(cursor, dict):
                continue
            chats[str(chat_id)] = ChatCursor(
                last_message_id=str(cursor.get("last_message_id") or ""),
                last_created=str(cursor.get("last_created") or ""),
                bootstrapped=bool(cursor.get("bootstrapped")),
            )

    return PollState(
        chats=chats,
        watching_since=str(data.get("watching_since") or ""),
        last_message_id=str(data.get("last_message_id") or ""),
        last_created=str(data.get("last_created") or ""),
        bootstrapped=bool(data.get("bootstrapped")),
    )


def save_state(path: Path, state: PollState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "watching_since": state.watching_since,
        "bootstrapped": state.bootstrapped,
        "last_message_id": state.last_message_id,
        "last_created": state.last_created,
        "chats": {
            chat_id: {
                "last_message_id": cursor.last_message_id,
                "last_created": cursor.last_created,
                "bootstrapped": cursor.bootstrapped,
            }
            for chat_id, cursor in state.chats.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_watching_since(state: PollState) -> PollState:
    """Marca el instante desde el cual vigilar mensajes nuevos (sin leer historial)."""
    if state.watching_since:
        return state
    return PollState(
        chats=state.chats,
        watching_since=utc_now_iso(),
        last_message_id=state.last_message_id,
        last_created=state.last_created,
        bootstrapped=True,
    )


def parse_graph_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def is_after_watching_since(created: str | None, watching_since: str) -> bool:
    if not watching_since:
        return True
    created_dt = parse_graph_datetime(created)
    since_dt = parse_graph_datetime(watching_since)
    if created_dt and since_dt:
        return created_dt >= since_dt
    return True


def is_newer_than_cursor(
    *,
    message_id: str,
    created: str | None,
    cursor: ChatCursor,
) -> bool:
    if not cursor.last_message_id and not cursor.last_created:
        return True
    created_dt = parse_graph_datetime(created)
    last_dt = parse_graph_datetime(cursor.last_created)
    if created_dt and last_dt:
        if created_dt > last_dt:
            return True
        if created_dt < last_dt:
            return False
        return message_id != cursor.last_message_id and message_id > cursor.last_message_id
    return message_id != cursor.last_message_id


# Compat helpers used by older single-chat path / tests
@dataclass
class LegacyPollState:
    last_message_id: str = ""
    last_created: str = ""
    bootstrapped: bool = False


def is_newer_than_state(
    *,
    message_id: str,
    created: str | None,
    state: LegacyPollState | ChatCursor | PollState,
) -> bool:
    if isinstance(state, PollState):
        cursor = ChatCursor(
            last_message_id=state.last_message_id,
            last_created=state.last_created,
            bootstrapped=state.bootstrapped,
        )
    elif isinstance(state, LegacyPollState):
        cursor = ChatCursor(
            last_message_id=state.last_message_id,
            last_created=state.last_created,
            bootstrapped=state.bootstrapped,
        )
    else:
        cursor = state
    return is_newer_than_cursor(message_id=message_id, created=created, cursor=cursor)


def mark_bootstrapped_now(path: Path) -> PollState:
    state = PollState(
        last_message_id="",
        last_created=utc_now_iso(),
        bootstrapped=True,
        watching_since=utc_now_iso(),
        chats={},
    )
    save_state(path, state)
    return state
