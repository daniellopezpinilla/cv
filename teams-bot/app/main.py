"""
Entrada legacy (webhook Bot Framework).

Modo recomendado sin Messaging endpoint de TI:
    python -m app.poller
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.handlers.offhours_guide import OffHoursGuideHandler
from app.handlers.router import HandlerRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("teams-bot")

app = FastAPI(
    title="Teams Off-Hours Support Bot",
    version="0.2.0",
    description="El modo activo es el poller (python -m app.poller). Este HTTP es opcional.",
)
app = FastAPI(title="Teams Off-Hours Support Bot", version="0.1.0")


def build_router() -> HandlerRouter:
    settings = get_settings()
    return HandlerRouter(
        handlers=[
            # v1 — fuera de horario: texto + PDF
            OffHoursGuideHandler(settings),
            # Futuro: UnlockUserHandler(settings), ChangeParamHandler(settings), ...
        ]
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
    return {"status": "ok"}


@app.post("/api/messages")
async def messages(request: Request) -> JSONResponse:
    """Webhook de Microsoft Bot Framework / Azure Bot."""
    activity: dict[str, Any] = await request.json()
    activity_type = activity.get("type", "")
    logger.info("Activity recibida: type=%s id=%s", activity_type, activity.get("id"))

    # Bot Framework espera 200/201/202; no fallar el webhook por lógica de negocio
    try:
        router = build_router()
        result = await router.dispatch(activity)
        logger.info("Dispatch: handled=%s detail=%s", result.handled, result.detail)
        return JSONResponse({"status": "ok", "handled": result.handled, "detail": result.detail})
    except Exception:
        logger.exception("Error procesando activity")
        return JSONResponse({"status": "error"}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
