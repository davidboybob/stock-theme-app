import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import get_settings

_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None
_lock = asyncio.Lock()


async def get_access_token() -> str:
    global _token, _token_expires_at

    async with _lock:
        if _token and _token_expires_at and datetime.now() < _token_expires_at:
            return _token

        settings = get_settings()
        url = f"{settings.kis_base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": settings.kis_app_key,
            "appsecret": settings.kis_app_secret,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        _token = data["access_token"]
        _token_expires_at = datetime.now() + timedelta(hours=23)
        return _token
