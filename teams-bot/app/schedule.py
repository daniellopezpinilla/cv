from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def is_off_hours(now: datetime | None = None, timezone: str = "America/Bogota") -> bool:
    """True fuera de horario laboral.

    Activo:
    - lunes a viernes: 18:00 inclusive hasta 05:59
    - sábado y domingo: todo el día
    """
    tz = ZoneInfo(timezone)
    moment = now.astimezone(tz) if now is not None else datetime.now(tz)

    # Saturday=5, Sunday=6
    if moment.weekday() >= 5:
        return True

    hour = moment.hour
    return hour >= 18 or hour < 6
