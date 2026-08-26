# Bot de soporte fuera de horario (Microsoft Teams)

Responde automáticamente **fuera de horario laboral (Bogotá)** con un mensaje y un **PDF** indicando que se debe crear un caso.

## Horario (America/Bogota)

| Cuándo | Bot |
|--------|-----|
| Lun–Vie 18:00–05:59 | Activo |
| Sábado y domingo (todo el día) | Activo |
| Lun–Vie 06:00–17:59 | Silencio (atiende el equipo) |

## Estructura (extensible)

```text
teams-bot/
  app/
    main.py                 # webhook /api/messages
    schedule.py             # regla de horario
    handlers/
      offhours_guide.py     # v1: texto + PDF
      # unlock_user.py      # futuro
    teams/                  # auth + reply Bot Framework
  assets/guia_crear_caso.pdf
```

Para agregar una función nueva: crea un `MessageHandler` y regístralo en `build_router()` en `app/main.py`.

## Requisitos

- Python 3.11+
- App Registration + Azure Bot en Microsoft
- Messaging endpoint HTTPS: `https://TU-DOMINIO/api/messages`
- Secretos solo en `.env` (nunca en Git)

## Setup en Windows dedicada

```powershell
cd teams-bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edita .env con MICROSOFT_APP_ID, MICROSOFT_APP_PASSWORD, etc.
# Reemplaza assets\guia_crear_caso.pdf por tu guía real
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check: `GET http://localhost:8000/health`

## Pruebas locales de horario

```powershell
pytest -q
```

## Seguridad

1. Rota cualquier `CLIENT_SECRET` que se haya pegado en chats o código.
2. No subas `.env` a GitHub.
3. El PDF de ejemplo en `assets/` es un placeholder; cámbialo por la guía oficial.
