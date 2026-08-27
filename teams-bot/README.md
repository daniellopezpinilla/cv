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

**Leer DMs:**
- `Chat.Read.All`
- `User.Read.All` (recomendado)

**Enviar respuestas (obligatorio — Graph lo exige explícitamente):**
- `ChatMessage.Send.All`

> `Chat.ReadWrite.All` **no basta** para enviar; Microsoft Graph responde 403 pidiendo `ChatMessage.Send.All`.

Opcional (canal): `ChannelMessage.Read.All`, `ChannelMessage.Send`

También puede requerir **CsApplicationAccessPolicy** en Teams (admin Teams).

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

## Modo rápido (DMs)

No recorre todo el historial al arrancar. Guarda `watching_since` y solo procesa mensajes **posteriores** a ese instante. Por ciclo revisa los chats 1:1 más recientes (`MAX_CHAT_PAGES=1` ≈ 50 chats).

Si migras de una versión lenta, borra `data/poll_state.json` una vez para reiniciar el punto de vigilancia.
