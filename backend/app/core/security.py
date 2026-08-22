from __future__ import annotations

from fastapi import Header, HTTPException
from app.core.config import get_settings


async def verify_alert_api_key(x_api_key: str = Header(...)) -> None:
    settings = get_settings()
    if not settings.alert_api_key:
        raise HTTPException(status_code=503, detail="ALERT_API_KEY not configured on server")
    if x_api_key != settings.alert_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
