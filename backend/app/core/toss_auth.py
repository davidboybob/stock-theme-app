"""토스증권 Open API OAuth 2.0 토큰 관리.

Client Credentials Grant로 access token을 발급받고 캐싱한다.
만료 60초 전에 자동 재발급하며, 동시 호출 시 중복 발급을 막기 위해 락을 사용한다.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from app.core.config import get_settings


class TossAuthError(Exception):
    pass


class TossTokenManager:
    def __init__(self):
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        # 만료 60초 전까지는 캐시 사용
        if self._token and time.monotonic() < self._expires_at - 60:
            return self._token

        async with self._lock:
            # 락 대기 중 다른 코루틴이 갱신했을 수 있음
            if self._token and time.monotonic() < self._expires_at - 60:
                return self._token
            await self._refresh()
            return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        """401(expired-token 등) 수신 시 강제 재발급 유도."""
        self._token = None
        self._expires_at = 0.0

    async def _refresh(self) -> None:
        settings = get_settings()
        if not settings.toss_client_id or not settings.toss_client_secret:
            raise TossAuthError(
                "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 이 .env 에 설정되지 않았습니다."
            )

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                f"{settings.toss_base_url}/oauth2/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.toss_client_id,
                    "client_secret": settings.toss_client_secret,
                },
            )

        if response.status_code != 200:
            raise TossAuthError(
                f"토스 토큰 발급 실패 (HTTP {response.status_code}): {response.text[:300]}"
            )

        data = response.json()
        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._expires_at = time.monotonic() + expires_in


_token_manager: TossTokenManager | None = None


def get_token_manager() -> TossTokenManager:
    global _token_manager
    if _token_manager is None:
        _token_manager = TossTokenManager()
    return _token_manager
