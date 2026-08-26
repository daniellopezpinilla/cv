from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings, get_settings
from app.handlers.offhours_guide import OffHoursGuideHandler
from app.handlers.router import HandlerRouter
from app.state import (
    PollState,
    is_newer_than_state,
    load_state,
    mark_bootstrapped_now,
    save_state,
)
from app.teams.graph import GraphTeamsClient
from app.teams.parse import graph_message_to_incoming

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("teams-bot.poller")


def build_graph(settings: Settings) -> GraphTeamsClient:
    return GraphTeamsClient(
        app_id=settings.app_id,
        app_password=settings.app_password,
        tenant_id=settings.tenant_id,
        chat_id=settings.teams_chat_id,
        team_id=settings.teams_team_id,
        channel_id=settings.teams_channel_id,
    )


def build_router(settings: Settings, graph: GraphTeamsClient) -> HandlerRouter:
    return HandlerRouter(
        handlers=[
            OffHoursGuideHandler(settings, graph),
            # Futuro: UnlockUserHandler(...), ChangeParamHandler(...), ...
        ]
    )


def _sort_oldest_first(raw_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        raw_messages,
        key=lambda m: (m.get("createdDateTime") or "", m.get("id") or ""),
    )


async def process_once(settings: Settings | None = None) -> int:
    """Una pasada de polling. Retorna cuántas respuestas automáticas envió."""
    settings = settings or get_settings()
    graph = build_graph(settings)
    router = build_router(settings, graph)
    state = load_state(settings.state_path)

    raw_messages = await graph.list_recent_messages(top=30)
    ordered = _sort_oldest_first(raw_messages)

    replied = 0
    bootstrap = not state.bootstrapped

    if bootstrap and not ordered:
        mark_bootstrapped_now(settings.state_path)
        logger.info("Bootstrap sin mensajes previos: listo para el próximo mensaje nuevo.")
        return 0

    for raw in ordered:
        msg_id = str(raw.get("id") or "")
        created = raw.get("createdDateTime")
        if not msg_id:
            continue
        if not is_newer_than_state(message_id=msg_id, created=created, state=state):
            continue

        incoming = graph_message_to_incoming(raw)

        # Primera corrida: solo marca el punto de partida (no responde histórico)
        if bootstrap:
            logger.info("Bootstrap: marcando mensaje %s como visto (sin responder)", msg_id)
        else:
            result = await router.dispatch(incoming)
            logger.info(
                "Mensaje %s de %s → handled=%s (%s)",
                msg_id,
                incoming.from_name or incoming.from_id,
                result.handled,
                result.detail,
            )
            if result.handled:
                replied += 1

        state = PollState(
            last_message_id=msg_id,
            last_created=str(created or ""),
            bootstrapped=True,
        )
        save_state(settings.state_path, state)

    if bootstrap:
        logger.info("Bootstrap terminado. Próximos mensajes nuevos sí se evaluarán.")

    return replied


async def run_forever() -> None:
    settings = get_settings()
    logger.info(
        "Poller iniciado mode=%s interval=%ss tz=%s",
        settings.target_mode,
        settings.poll_interval_seconds,
        settings.timezone,
    )
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
