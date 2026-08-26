"""
Entrada legacy (webhook Bot Framework).

Modo recomendado sin Messaging endpoint de TI:
    python -m app.poller
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("teams-bot")

app = FastAPI(
    title="Teams Off-Hours Support Bot",
    version="0.2.0",
    description="El modo activo es el poller (python -m app.poller). Este HTTP es opcional.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "use python -m app.poller"}


@app.post("/api/messages")
async def messages_deprecated() -> dict[str, str]:
    logger.warning(
        "Se recibió /api/messages pero el bot corre en modo poller (sin Messaging endpoint)."
    )
    return {
        "status": "deprecated",
        "detail": "Usa python -m app.poller. No se requiere Messaging endpoint.",
    }


if __name__ == "__main__":
    logger.info("Arranca el poller con: python -m app.poller")
