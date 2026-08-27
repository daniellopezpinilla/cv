# Bot de soporte fuera de horario (Microsoft Teams) — modo poller

Responde automáticamente **fuera de horario laboral (Bogotá)** con un mensaje y un **PDF** indicando que se debe crear un caso.

> No requiere Messaging endpoint. Corre en la Windows dedicada y consulta Teams vía Microsoft Graph.

## Caso real: mensajes directos a la cuenta de soporte

Cada persona que escribe a `soporte@...` abre un **chat 1:1 distinto**.  
Por eso **no** uses un solo `TEAMS_CHAT_ID`. Usa:

```env
SUPPORT_USER_ID=soporteAppsHalliburton@ecopetrol.com.co
```

El poller lista todos los chats `oneOnOne` de esa cuenta y responde en cada uno.

## Horario (America/Bogota)

| Cuándo | Bot |
|--------|-----|
| Lun–Vie 18:00–05:59 | Activo |
| Sábado y domingo (todo el día) | Activo |
| Lun–Vie 06:00–17:59 | Silencio |

Prueba en horario laboral: `FORCE_OFF_HOURS=true` en `.env` (quítalo después).

## Permisos Graph (Aplicación + admin consent)

Mínimo para DMs:
- `Chat.Read.All`
- `Chat.ReadWrite.All`

Recomendado:
- `User.Read.All` (resolver el usuario de soporte y no auto-responderse)
- `ChannelMessage.Read.All` / `ChannelMessage.Send` (si más adelante usan canal)

## Setup

```powershell
cd teams-bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edita .env: App ID, secret, tenant, SUPPORT_USER_ID
# Reemplaza assets\guia_crear_caso.pdf
Remove-Item .\data\poll_state.json -ErrorAction SilentlyContinue
python -m app.poller
```

## Cómo obtener SUPPORT_USER_ID

1. El correo de la cuenta de soporte (UPN), p. ej. `soporteAppsHalliburton@ecopetrol.com.co`, **o**
2. En Entra ID → Users → esa cuenta → **Object ID** (GUID)

## Pruebas

```powershell
pytest -q
```
