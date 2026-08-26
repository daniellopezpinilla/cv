# Bot de soporte fuera de horario (Microsoft Teams) — modo poller

Responde automáticamente **fuera de horario laboral (Bogotá)** con un mensaje y un **PDF** indicando que se debe crear un caso.

> **Cambio de plan:** no requiere Messaging endpoint ni URL pública de TI.  
> El programa corre en la **Windows dedicada** y **consulta Teams** vía Microsoft Graph.

## Horario (America/Bogota)

| Cuándo | Bot |
|--------|-----|
| Lun–Vie 18:00–05:59 | Activo |
| Sábado y domingo (todo el día) | Activo |
| Lun–Vie 06:00–17:59 | Silencio (atiende el equipo; igual marca mensajes como vistos) |

## Cómo funciona

```text
Windows dedicada
  → cada N segundos pregunta a Graph: ¿hay mensajes nuevos?
  → si es fuera de horario → responde texto + PDF
  → si es horario laboral → no responde (solo avanza el cursor)
```

## Permisos Graph (App Registration) — pedir admin consent

Para **canal**:
- `ChannelMessage.Read.All`
- `ChannelMessage.Send`

Para **chat**:
- `Chat.Read.All`
- `Chat.ReadWrite` o `Chat.ReadWrite.All` (según lo que permita el tenant)

Tipo: **Application permissions** + **Grant admin consent**.

## Setup en Windows dedicada

```powershell
cd teams-bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env`:
1. `MICROSOFT_APP_ID`, `MICROSOFT_APP_PASSWORD`, `MICROSOFT_APP_TENANT_ID`
2. `TEAMS_CHAT_ID` **o** `TEAMS_TEAM_ID` + `TEAMS_CHANNEL_ID`
3. Reemplaza `assets\guia_crear_caso.pdf` por tu guía real

Arranque:

```powershell
python -m app.poller
```

Deja el proceso corriendo (Task Scheduler al inicio de Windows).

## Cómo obtener el Chat ID / Channel ID

1. Abre [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer) con una cuenta que vea el chat/canal.
2. Chat: `GET https://graph.microsoft.com/v1.0/me/chats` y copia el `id`.
3. Canal: `GET https://graph.microsoft.com/v1.0/teams` → luego  
   `GET https://graph.microsoft.com/v1.0/teams/{team-id}/channels`.

## Estructura (extensible)

```text
app/
  poller.py              # entrada principal (sin URL pública)
  schedule.py            # horario Bogotá
  handlers/offhours_guide.py
  teams/graph.py         # leer/enviar vía Graph
```

Función nueva = nuevo `MessageHandler` registrado en `build_router()` dentro de `poller.py`.

## Pruebas

```powershell
pytest -q
```

## Seguridad

1. Rota cualquier secret que se haya compartido.
2. No subas `.env` ni `data/poll_state.json` a GitHub.
3. El PDF en `assets/` es placeholder.
