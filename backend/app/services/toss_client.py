"""토스증권 Open API REST 클라이언트.

- OAuth 토큰 자동 첨부/갱신 (401 시 1회 재발급 후 재시도)
- API 그룹별 클라이언트 사이드 rate limiter (토큰 버킷)
- 429 수신 시 Retry-After 기반 재시도 + 지수 백오프
- 에러 envelope({"error": {...}}) 파싱 → TossApiError
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.toss_auth import get_token_manager


class TossApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, data: Any = None, request_id: str | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data
        self.request_id = request_id
        super().__init__(f"[{status_code}/{code}] {message}")


class _RateLimiter:
    """단순 토큰 버킷. rate = 초당 허용 요청 수."""

    def __init__(self, rate: float):
        self.rate = rate
        # rate < 1(예: ACCOUNT 0.8)이면 버킷 상한이 1 미만이 되어 영원히
        # 토큰이 모이지 않으므로, 상한은 최소 1을 보장해야 한다
        self.capacity = max(rate, 1.0)
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) / self.rate)


# 문서 기준 그룹별 TPS (여유를 두고 80% 수준으로 설정)
_GROUP_RATES = {
    "AUTH": 4.0,
    "ACCOUNT": 0.8,
    "ASSET": 4.0,
    "STOCK": 4.0,
    "MARKET_INFO": 2.4,
    "MARKET_DATA": 8.0,
    "MARKET_DATA_CHART": 4.0,
    "ORDER": 4.0,
    "ORDER_HISTORY": 4.0,
    "ORDER_INFO": 4.0,
}

_limiters: dict[str, _RateLimiter] = {}


def _limiter(group: str) -> _RateLimiter:
    if group not in _limiters:
        _limiters[group] = _RateLimiter(_GROUP_RATES.get(group, 2.0))
    return _limiters[group]


class TossClient:
    MAX_RETRIES = 3

    def __init__(self):
        self.settings = get_settings()
        self.auth = get_token_manager()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        group: str,
        account_seq: int | None = None,
        params: dict | None = None,
        json: dict | None = None,
    ) -> Any:
        url = f"{self.settings.toss_base_url}{path}"
        retried_auth = False

        for attempt in range(self.MAX_RETRIES + 1):
            await _limiter(group).acquire()

            headers = {"Authorization": f"Bearer {await self.auth.get_token()}"}
            if account_seq is not None:
                headers["X-Tossinvest-Account"] = str(account_seq)

            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.request(method, url, headers=headers, params=params, json=json)

            if response.status_code < 400:
                return response.json()

            # 401 → 토큰 재발급 후 1회 재시도
            if response.status_code == 401 and not retried_auth:
                self.auth.invalidate()
                retried_auth = True
                continue

            # 429 → Retry-After 대기 후 재시도 (지수 백오프 겸용)
            if response.status_code == 429 and attempt < self.MAX_RETRIES:
                retry_after = float(response.headers.get("Retry-After", 2 ** attempt))
                await asyncio.sleep(min(retry_after, 10.0))
                continue

            raise self._to_error(response)

        raise self._to_error(response)

    @staticmethod
    def _to_error(response: httpx.Response) -> TossApiError:
        try:
            err = response.json().get("error", {})
        except Exception:
            err = {}
        return TossApiError(
            status_code=response.status_code,
            code=err.get("code", "unknown"),
            message=err.get("message", response.text[:200]),
            data=err.get("data"),
            request_id=err.get("requestId") or response.headers.get("X-Request-Id"),
        )

    # ── 계좌·자산 ──────────────────────────────────────────

    async def get_accounts(self) -> list[dict]:
        data = await self._request("GET", "/api/v1/accounts", group="ACCOUNT")
        return data.get("result", data) if isinstance(data, dict) else data

    async def get_holdings(self, account_seq: int, symbol: str | None = None) -> dict:
        params = {"symbol": symbol} if symbol else None
        data = await self._request(
            "GET", "/api/v1/holdings", group="ASSET", account_seq=account_seq, params=params
        )
        return data.get("result", data)

    # ── 주문 ──────────────────────────────────────────────

    async def create_order(self, account_seq: int, payload: dict) -> dict:
        data = await self._request(
            "POST", "/api/v1/orders", group="ORDER", account_seq=account_seq, json=payload
        )
        return data.get("result", data)

    async def modify_order(self, account_seq: int, order_id: str, payload: dict) -> dict:
        data = await self._request(
            "POST", f"/api/v1/orders/{order_id}/modify", group="ORDER",
            account_seq=account_seq, json=payload,
        )
        return data.get("result", data)

    async def cancel_order(self, account_seq: int, order_id: str) -> dict:
        data = await self._request(
            "POST", f"/api/v1/orders/{order_id}/cancel", group="ORDER",
            account_seq=account_seq, json={},
        )
        return data.get("result", data)

    async def get_open_orders(self, account_seq: int, symbol: str | None = None) -> dict:
        params: dict = {"status": "OPEN"}
        if symbol:
            params["symbol"] = symbol
        data = await self._request(
            "GET", "/api/v1/orders", group="ORDER_HISTORY",
            account_seq=account_seq, params=params,
        )
        return data.get("result", data)

    async def get_order(self, account_seq: int, order_id: str) -> dict:
        data = await self._request(
            "GET", f"/api/v1/orders/{order_id}", group="ORDER_HISTORY", account_seq=account_seq
        )
        return data.get("result", data)

    async def get_buying_power(self, account_seq: int, currency: str = "KRW") -> dict:
        data = await self._request(
            "GET", "/api/v1/buying-power", group="ORDER_INFO",
            account_seq=account_seq, params={"currency": currency},
        )
        return data.get("result", data)

    async def get_sellable_quantity(self, account_seq: int, symbol: str) -> dict:
        data = await self._request(
            "GET", "/api/v1/sellable-quantity", group="ORDER_INFO",
            account_seq=account_seq, params={"symbol": symbol},
        )
        return data.get("result", data)

    async def get_commissions(self, account_seq: int) -> dict:
        data = await self._request(
            "GET", "/api/v1/commissions", group="ORDER_INFO", account_seq=account_seq
        )
        return data.get("result", data)

    # ── 시세 (Phase 2+에서 사용) ──────────────────────────

    async def get_prices(self, symbols: list[str]) -> Any:
        data = await self._request(
            "GET", "/api/v1/prices", group="MARKET_DATA", params={"symbols": ",".join(symbols)}
        )
        return data.get("result", data)

    async def get_orderbook(self, symbol: str) -> Any:
        data = await self._request(
            "GET", "/api/v1/orderbook", group="MARKET_DATA", params={"symbol": symbol}
        )
        return data.get("result", data)

    async def get_kr_market_calendar(self) -> Any:
        data = await self._request("GET", "/api/v1/market-calendar/KR", group="MARKET_INFO")
        return data.get("result", data)


_client: TossClient | None = None


def get_toss_client() -> TossClient:
    global _client
    if _client is None:
        _client = TossClient()
    return _client
