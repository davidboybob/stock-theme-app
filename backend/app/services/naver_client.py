from __future__ import annotations

import asyncio
import httpx
from app.core.config import get_settings
from app.models.stock import StockPrice, IndexPrice

_semaphore = asyncio.Semaphore(10)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://finance.naver.com/",
}


def _parse_number(value: str) -> float:
    try:
        return float(value.replace(",", "").replace("%", "").strip())
    except (ValueError, AttributeError):
        return 0.0


class NaverClient:
    def __init__(self):
        self.settings = get_settings()

    async def get_stock_price(self, code: str) -> StockPrice:
        url = f"{self.settings.naver_base_url}/api/realtime/domestic/stock/{code}"
        async with _semaphore:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.get(url, headers=HEADERS)
                response.raise_for_status()
                data = response.json()

        item = data["datas"][0]
        current = _parse_number(item.get("closePrice", "0"))
        change = _parse_number(item.get("compareToPreviousClosePrice", "0"))
        change_rate = _parse_number(item.get("fluctuationsRatio", "0"))
        direction = item.get("compareToPreviousPrice", {}).get("name", "")
        if direction == "FALLING" and change > 0:
            change = -change
        if direction == "FALLING" and change_rate > 0:
            change_rate = -change_rate

        return StockPrice(
            code=code,
            name=item.get("stockName", ""),
            current_price=int(current),
            change_price=int(change),
            change_rate=change_rate,
            volume=int(_parse_number(item.get("accumulatedTradingVolume", "0"))),
            high_price=int(_parse_number(item.get("highPrice", "0"))),
            low_price=int(_parse_number(item.get("lowPrice", "0"))),
            open_price=int(_parse_number(item.get("openPrice", "0"))),
        )

    async def get_index_price(self, index_code: str) -> IndexPrice:
        index_names = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ"}
        url = f"{self.settings.naver_base_url}/api/realtime/domestic/index/{index_code}"
        async with _semaphore:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.get(url, headers=HEADERS)
                response.raise_for_status()
                data = response.json()

        item = data["datas"][0]
        current = _parse_number(item.get("closePrice", "0"))
        change = _parse_number(item.get("compareToPreviousClosePrice", "0"))
        change_rate = _parse_number(item.get("fluctuationsRatio", "0"))
        direction = item.get("compareToPreviousPrice", {}).get("name", "")
        if direction == "FALLING" and change > 0:
            change = -change
        if direction == "FALLING" and change_rate > 0:
            change_rate = -change_rate

        return IndexPrice(
            code=index_code,
            name=index_names.get(index_code, index_code),
            current_value=current,
            change_value=change,
            change_rate=change_rate,
        )


naver_client = NaverClient()
