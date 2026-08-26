from __future__ import annotations

import time

import httpx

_SCOPE = "https://api.botframework.com/.default"

_cached_token: str | None = None
_cached_expires_at: float = 0.0


def _token_url(tenant_id: str | None = None) -> str:
    # Single-tenant: usa el tenant. Multi-tenant: botframework.com
    authority = tenant_id.strip() if tenant_id and tenant_id.strip() else "botframework.com"
    return f"https://login.microsoftonline.com/{authority}/oauth2/v2.0/token"


async def get_bot_framework_token(
    app_id: str,
    app_password: str,
    tenant_id: str | None = None,
) -> str:
    """Obtiene token OAuth para el Bot Connector."""
    global _cached_token, _cached_expires_at

    now = time.time()
    if _cached_token and now < _cached_expires_at - 60:
        return _cached_token

    data = {
        "grant_type": "client_credentials",
        "client_id": app_id,
        "client_secret": app_password,
        "scope": _SCOPE,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(_token_url(tenant_id), data=data)
        response.raise_for_status()
        payload = response.json()

    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"No se obtuvo access_token: {payload}")

    expires_in = int(payload.get("expires_in", 3600))
    _cached_token = token
    _cached_expires_at = now + expires_in
    return token
