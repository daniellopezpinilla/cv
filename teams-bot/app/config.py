from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent


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
    host: str
    port: int


def get_settings() -> Settings:
    pdf_raw = os.getenv("PDF_PATH", "assets/guia_crear_caso.pdf").strip()
    pdf_path = Path(pdf_raw)
    if not pdf_path.is_absolute():
        pdf_path = ROOT_DIR / pdf_path

    reply = os.getenv(
        "REPLY_TEXT",
        (
            "Hola, este es el soporte automático de Aplicaciones.\n\n"
            "Actualmente estamos fuera de horario laboral "
            "(lunes a viernes 6:00 p.m. – 6:00 a.m., y fines de semana). "
            "Por favor crea un caso siguiendo la guía adjunta. "
            "Tu solicitud será atendida en el próximo día hábil."
        ),
    ).replace("\\n", "\n")

    return Settings(
        app_id=_env("MICROSOFT_APP_ID"),
        app_password=_env("MICROSOFT_APP_PASSWORD"),
        tenant_id=os.getenv("MICROSOFT_APP_TENANT_ID", "").strip(),
        timezone=os.getenv("TIMEZONE", "America/Bogota").strip() or "America/Bogota",
        reply_text=reply,
        pdf_path=pdf_path,
        pdf_filename=os.getenv("PDF_FILENAME", "guia_crear_caso.pdf").strip()
        or "guia_crear_caso.pdf",
        host=os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
