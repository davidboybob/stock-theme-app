from __future__ import annotations

import httpx
import xml.etree.ElementTree as ET
import asyncio
from datetime import datetime, timedelta
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

CHART_URL = "https://fchart.stock.naver.com/sise.nhn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://finance.naver.com/",
}

_semaphore = asyncio.Semaphore(5)

_cache: dict[str, tuple[list[int], datetime]] = {}
_CACHE_TTL = timedelta(minutes=5)


async def get_daily_close_prices(code: str, count: int = 30) -> list[int]:
    """네이버 금융 차트 API에서 일봉 종가 리스트 반환 (최신순 정렬).

    Returns: 최신 → 과거 순서의 종가 리스트 (int)
    """
    cache_key = f"{code}:{count}"
    cached = _cache.get(cache_key)
    if cached is not None:
        prices, cached_at = cached
        if datetime.now() - cached_at < _CACHE_TTL:
            return prices

    params = {
        "symbol": code,
        "timeframe": "day",
        "count": str(count),
        "requestType": "0",
    }

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    ):
        with attempt:
            async with _semaphore:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(CHART_URL, params=params, headers=HEADERS)
                    response.raise_for_status()
                    xml_text = response.text

    root = ET.fromstring(xml_text)
    prices = []
    for item in root.findall(".//item"):
        data = item.get("data", "")
        parts = data.split("|")
        # format: date|open|high|low|close|volume
        if len(parts) >= 5:
            try:
                close = int(float(parts[4].replace(",", "")))
                if close > 0:
                    prices.append(close)
            except (ValueError, IndexError):
                continue

    # 최신순 정렬 (XML은 과거→최신 순서)
    prices.reverse()
    _cache[cache_key] = (prices, datetime.now())
    return prices
