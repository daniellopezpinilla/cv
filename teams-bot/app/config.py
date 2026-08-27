from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_REPLY = (
    "Hola, este es el soporte automático de Aplicaciones.\n\n"
    "Actualmente estamos fuera de horario laboral "
    "(lunes a viernes 6:00 p.m. – 6:00 a.m., y fines de semana). "
    "Por favor crea un caso siguiendo la guía adjunta. "
    "Tu solicitud será atendida en el próximo día hábil."
)


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Falta la variable de entorno requerida: {name}")
    return value.strip()


@dataclass(frozen=True)
class Settings:
    app_id: str
    app_password: str
    tenant_id: str
    timezone: str
    reply_text: str
    pdf_path: Path
    pdf_filename: str
    # Modos de destino (elige uno)
    support_user_id: str  # UPN o object id de la cuenta de soporte (DMs)
    teams_chat_id: str  # un solo chat (legacy / prueba)
    teams_team_id: str
    teams_channel_id: str
    poll_interval_seconds: int
    state_path: Path
    force_off_hours: bool
    max_chat_pages: int
    messages_per_chat: int
    host: str
    port: int

    @property
    def target_mode(self) -> str:
        if self.support_user_id:
            return "support_dms"
        if self.teams_chat_id:
            return "chat"
        if self.teams_team_id and self.teams_channel_id:
            return "channel"
        raise RuntimeError(
            "Configura SUPPORT_USER_ID (recomendado para DMs), "
            "TEAMS_CHAT_ID, o TEAMS_TEAM_ID + TEAMS_CHANNEL_ID"
        )


def get_settings() -> Settings:
    pdf_raw = os.getenv("PDF_PATH", "assets/guia_crear_caso.pdf").strip()
    pdf_path = Path(pdf_raw)
    if not pdf_path.is_absolute():
        pdf_path = ROOT_DIR / pdf_path

    state_raw = os.getenv("STATE_PATH", "data/poll_state.json").strip()
    state_path = Path(state_raw)
    if not state_path.is_absolute():
        state_path = ROOT_DIR / state_path

    reply = os.getenv("REPLY_TEXT", DEFAULT_REPLY).replace("\\n", "\n")
    force = os.getenv("FORCE_OFF_HOURS", "").strip().lower() in {"1", "true", "yes", "si", "sí"}

    settings = Settings(
        app_id=_env("MICROSOFT_APP_ID"),
        app_password=_env("MICROSOFT_APP_PASSWORD"),
        tenant_id=_env("MICROSOFT_APP_TENANT_ID"),
        timezone=os.getenv("TIMEZONE", "America/Bogota").strip() or "America/Bogota",
        reply_text=reply,
        pdf_path=pdf_path,
        pdf_filename=os.getenv("PDF_FILENAME", "guia_crear_caso.pdf").strip()
        or "guia_crear_caso.pdf",
        support_user_id=os.getenv("SUPPORT_USER_ID", "").strip(),
        teams_chat_id=os.getenv("TEAMS_CHAT_ID", "").strip(),
        teams_team_id=os.getenv("TEAMS_TEAM_ID", "").strip(),
        teams_channel_id=os.getenv("TEAMS_CHANNEL_ID", "").strip(),
        poll_interval_seconds=max(15, int(os.getenv("POLL_INTERVAL_SECONDS", "60"))),
        state_path=state_path,
        force_off_hours=force,
        max_chat_pages=max(1, int(os.getenv("MAX_CHAT_PAGES", "1"))),
        messages_per_chat=max(3, int(os.getenv("MESSAGES_PER_CHAT", "5"))),
        host=os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
    _ = settings.target_mode
    return settings
