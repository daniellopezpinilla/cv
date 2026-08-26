from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.schedule import is_off_hours

TZ = "America/Bogota"


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(TZ))


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        # Viernes 18:00 → activo
        (_dt(2026, 3, 20, 18, 0), True),
        # Viernes 17:59 → inactivo
        (_dt(2026, 3, 20, 17, 59), False),
        # Lunes 05:59 → activo
        (_dt(2026, 3, 16, 5, 59), True),
        # Lunes 06:00 → inactivo
        (_dt(2026, 3, 16, 6, 0), False),
        # Sábado mediodía → activo
        (_dt(2026, 3, 21, 12, 0), True),
        # Domingo noche → activo
        (_dt(2026, 3, 22, 22, 0), True),
        # Miércoles 10:00 → inactivo
        (_dt(2026, 3, 18, 10, 0), False),
    ],
)
def test_is_off_hours(moment: datetime, expected: bool) -> None:
    assert is_off_hours(moment, timezone=TZ) is expected
