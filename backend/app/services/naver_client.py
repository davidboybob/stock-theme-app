from __future__ import annotations

import asyncio
import re
import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type
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
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
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
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
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

    async def get_stock_detail(self, code: str) -> dict:
        """네이버 증권 종목 상세 페이지에서 추가 정보 파싱"""
        from bs4 import BeautifulSoup
        url = "https://finance.naver.com/item/main.naver"
        headers = {
            "Referer": "https://finance.naver.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
        result: dict = {
            "code": code,
            "week52_high": None,
            "week52_low": None,
            "per": None,
            "pbr": None,
            "market_cap": None,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, params={"code": code}, headers=headers)
                resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # PER
            for em in soup.select("em#_per"):
                try:
                    result["per"] = float(em.get_text(strip=True).replace(",", ""))
                except Exception:
                    pass

            # PBR
            for em in soup.select("em#_pbr"):
                try:
                    result["pbr"] = float(em.get_text(strip=True).replace(",", ""))
                except Exception:
                    pass

            # 52주 최고/최저 — summary="투자의견 정보" 테이블 내 "52주최고" th 행
            # th 안에 span 자식이 있어 string 매칭이 안 되므로 get_text()로 검색
            invest_table = soup.find("table", {"summary": "투자의견 정보"})
            if invest_table:
                week_th = None
                for th in invest_table.find_all("th"):
                    if "52주최고" in th.get_text(strip=True):
                        week_th = th
                        break
                if week_th:
                    week_td = week_th.find_next_sibling("td")
                    if week_td:
                        ems = week_td.find_all("em")
                        if len(ems) >= 1:
                            try:
                                result["week52_high"] = int(ems[0].get_text(strip=True).replace(",", ""))
                            except Exception:
                                pass
                        if len(ems) >= 2:
                            try:
                                result["week52_low"] = int(ems[1].get_text(strip=True).replace(",", ""))
                            except Exception:
                                pass

            # 시가총액 — "1,027조 572" 형태 파싱
            market_sum_em = soup.select_one("em#_market_sum")
            if market_sum_em:
                raw = market_sum_em.get_text(separator=" ", strip=True)
                jo_match = re.search(r"([\d,]+)조", raw)
                eok_match = re.search(r"조\s*([\d,]+)", raw)
                jo_val = int(jo_match.group(1).replace(",", "")) if jo_match else 0
                eok_val = int(eok_match.group(1).replace(",", "")) if eok_match else 0
                if jo_val > 0 or eok_val > 0:
                    result["market_cap"] = (jo_val * 10_000 + eok_val) * 100_000_000
        except Exception:
            pass

        return result


naver_client = NaverClient()
