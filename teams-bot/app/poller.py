from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings, get_settings
from app.handlers.offhours_guide import OffHoursGuideHandler
from app.handlers.router import HandlerRouter
from app.state import (
    ChatCursor,
    PollState,
    ensure_watching_since,
    is_after_watching_since,
    is_newer_than_cursor,
    load_state,
    mark_bootstrapped_now,
    save_state,
)
from app.teams.graph import GraphTeamsClient
from app.teams.parse import graph_message_to_incoming, is_user_chat_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("teams-bot.poller")


def build_graph(settings: Settings) -> GraphTeamsClient:
    return GraphTeamsClient(
        app_id=settings.app_id,
        app_password=settings.app_password,
        tenant_id=settings.tenant_id,
        support_user_id=settings.support_user_id,
        chat_id=settings.teams_chat_id,
        team_id=settings.teams_team_id,
        channel_id=settings.teams_channel_id,
    )


def build_router(settings: Settings, graph: GraphTeamsClient) -> HandlerRouter:
    return HandlerRouter(
        handlers=[
            OffHoursGuideHandler(settings, graph),
        ]
    )


def _sort_oldest_first(raw_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        raw_messages,
        key=lambda m: (m.get("createdDateTime") or "", m.get("id") or ""),
    )


def _merge_tracked_chats(
    api_chats: list[dict[str, Any]],
    state: PollState,
) -> list[dict[str, Any]]:
    """Une chats recientes de Graph con chats ya vigilados en estado."""
    by_id: dict[str, dict[str, Any]] = {}
    for chat in api_chats:
        cid = str(chat.get("id") or "")
        if cid:
            by_id[cid] = chat
    for chat_id in state.chats:
        if chat_id not in by_id:
            by_id[chat_id] = {"id": chat_id, "chatType": "oneOnOne"}
    return list(by_id.values())


async def _process_chat_messages(
    *,
    chat_id: str,
    raw_messages: list[dict[str, Any]],
    cursor: ChatCursor,
    router: HandlerRouter,
    support_object_id: str = "",
    watching_since: str = "",
    legacy_bootstrap: bool = False,
) -> tuple[ChatCursor, int]:
    ordered = _sort_oldest_first(raw_messages)
    replied = 0
    bootstrap = legacy_bootstrap and not cursor.bootstrapped

    if bootstrap and not ordered:
        return (
            ChatCursor(
                last_message_id="",
                last_created=cursor.last_created,
                bootstrapped=True,
            ),
            0,
        )

    for raw in ordered:
        msg_id = str(raw.get("id") or "")
        created = raw.get("createdDateTime")
        if not msg_id:
            continue

        if not is_user_chat_message(raw):
            continue

        if watching_since and not is_after_watching_since(created, watching_since):
            continue

        if not is_newer_than_cursor(message_id=msg_id, created=created, cursor=cursor):
            continue

        incoming = graph_message_to_incoming(raw, chat_id=chat_id)

        if bootstrap:
            logger.info(
                "Bootstrap chat=%s mensaje=%s (sin responder)",
                chat_id[:24],
                msg_id,
            )
        elif support_object_id and incoming.from_id == support_object_id:
            logger.info(
                "Chat %s | mensaje %s de soporte (ignorado)",
                chat_id[:24],
                msg_id,
            )
        else:
            try:
                result = await router.dispatch(incoming)
                logger.info(
                    "Chat %s | mensaje %s de %s → handled=%s (%s)",
                    chat_id[:24],
                    msg_id,
                    incoming.from_name or incoming.from_id,
                    result.handled,
                    result.detail,
                )
                if result.handled:
                    replied += 1
            except Exception:
                logger.exception(
                    "Error respondiendo en chat %s al mensaje %s",
                    chat_id[:24],
                    msg_id,
                )

        cursor = ChatCursor(
            last_message_id=msg_id,
            last_created=str(created or ""),
            bootstrapped=True,
        )

    if ordered and not cursor.bootstrapped:
        # Marcar chat visto sin mensajes nuevos (evita re-leer cada ciclo)
        last = ordered[-1]
        cursor = ChatCursor(
            last_message_id=str(last.get("id") or ""),
            last_created=str(last.get("createdDateTime") or ""),
            bootstrapped=True,
        )

    return cursor, replied


async def process_support_dms(settings: Settings, graph: GraphTeamsClient) -> int:
    router = build_router(settings, graph)
    state = load_state(settings.state_path)

    prev_watching = state.watching_since
    state = ensure_watching_since(state)
    if not prev_watching:
        save_state(settings.state_path, state)
        logger.info(
            "Modo rápido activo: solo mensajes nuevos desde %s (sin recorrer historial).",
            state.watching_since,
        )

    support_object_id = ""
    try:
        support_object_id = await graph.resolve_user_object_id(settings.support_user_id)
    except Exception:
        logger.warning(
            "No se pudo resolver SUPPORT_USER_ID=%s (¿falta User.Read.All?). "
            "Se continúa sin filtrar mensajes de la cuenta soporte.",
            settings.support_user_id,
        )

    chats = await graph.list_support_one_on_one_chats(
        max_pages=settings.max_chat_pages,
    )
    chats = _merge_tracked_chats(chats, state)
    logger.info(
        "DMs a revisar: %s chats oneOnOne (API + vigilados, máx %s página(s))",
        len(chats),
        settings.max_chat_pages,
    )

    replied_total = 0
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            continue

        cursor = state.chats.get(chat_id) or ChatCursor()

        try:
            messages = await graph.list_chat_messages(
                chat_id,
                top=settings.messages_per_chat,
            )
        except Exception:
            logger.exception("No se pudieron leer mensajes del chat %s", chat_id[:40])
            continue

        new_cursor, replied = await _process_chat_messages(
            chat_id=chat_id,
            raw_messages=messages,
            cursor=cursor,
            router=router,
            support_object_id=support_object_id,
            watching_since=state.watching_since,
            legacy_bootstrap=False,
        )
        state.chats[chat_id] = new_cursor
        replied_total += replied

    if replied_total:
        logger.info("Respuestas automáticas enviadas en este ciclo: %s", replied_total)

    state.bootstrapped = True
    save_state(settings.state_path, state)
    return replied_total


async def process_single_target(settings: Settings, graph: GraphTeamsClient) -> int:
    """Modo legacy: un chat o un canal."""
    router = build_router(settings, graph)
    state = load_state(settings.state_path)
    chat_key = settings.teams_chat_id or f"{settings.teams_team_id}/{settings.teams_channel_id}"
    cursor = state.chats.get(chat_key)
    if cursor is None and (state.last_message_id or state.bootstrapped):
        cursor = ChatCursor(
            last_message_id=state.last_message_id,
            last_created=state.last_created,
            bootstrapped=state.bootstrapped,
        )
    cursor = cursor or ChatCursor()

    raw_messages = await graph.list_recent_messages(top=30)
    if not cursor.bootstrapped and not raw_messages:
        mark_bootstrapped_now(settings.state_path)
        logger.info("Bootstrap sin mensajes previos: listo para el próximo mensaje nuevo.")
        return 0

    was_bootstrap = not cursor.bootstrapped
    new_cursor, replied = await _process_chat_messages(
        chat_id=settings.teams_chat_id,
        raw_messages=raw_messages,
        cursor=cursor,
        router=router,
        support_object_id="",
        legacy_bootstrap=True,
    )
    state.chats[chat_key] = new_cursor
    state.last_message_id = new_cursor.last_message_id
    state.last_created = new_cursor.last_created
    state.bootstrapped = new_cursor.bootstrapped
    save_state(settings.state_path, state)

    if was_bootstrap:
        logger.info("Bootstrap terminado. Próximos mensajes nuevos sí se evaluarán.")
    return replied


async def process_once(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    graph = build_graph(settings)
    if settings.target_mode == "support_dms":
        return await process_support_dms(settings, graph)
    return await process_single_target(settings, graph)


async def run_forever() -> None:
    settings = get_settings()
    logger.info(
        "Poller iniciado mode=%s interval=%ss tz=%s force_off_hours=%s pages=%s",
        settings.target_mode,
        settings.poll_interval_seconds,
        settings.timezone,
        settings.force_off_hours,
        settings.max_chat_pages,
    )
    if settings.target_mode == "support_dms":
        logger.info("Vigilando DMs de SUPPORT_USER_ID=%s", settings.support_user_id)
    while True:
        try:
            await process_once(settings)
        except Exception:
            logger.exception("Error en ciclo de polling; se reintentará")
        await asyncio.sleep(settings.poll_interval_seconds)


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
