import asyncio
import time
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException
from typing import List
from app.models.stock import StockPrice, IndexPrice
from app.services.naver_client import naver_client

router = APIRouter(tags=["stocks"])

# 지수는 30초 캐시 — 대시보드 진입마다 외부 호출이 나가지 않도록
_INDICES_TTL = 30.0
_indices_cache: dict = {"data": None, "ts": 0.0}

# 네이버 지수 API는 해외 IP(Render 등)에서 datas가 빈 배열로 온다 — 야후를 대체 소스로 사용
_YAHOO_INDEX_SYMBOLS = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}


async def _yahoo_index_price(index_code: str) -> IndexPrice:
    symbol = quote(_YAHOO_INDEX_SYMBOLS[index_code], safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            url,
            params={"interval": "1d", "range": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
    price = float(meta["regularMarketPrice"])
    prev = float(meta.get("chartPreviousClose") or 0)
    change = price - prev if prev else 0.0
    rate = (change / prev * 100) if prev else 0.0
    return IndexPrice(
        code=index_code,
        name=index_code,
        current_value=round(price, 2),
        change_value=round(change, 2),
        change_rate=round(rate, 2),
    )


async def _fetch_index(index_code: str) -> IndexPrice:
    try:
        return await naver_client.get_index_price(index_code)
    except Exception:
        return await _yahoo_index_price(index_code)


@router.get("/stocks/search")
async def search_stocks(q: str):
    """네이버 증권 자동완성 API로 종목 검색"""
    if not q or len(q.strip()) < 1:
        return []
    url = "https://ac.stock.naver.com/ac"
    params = {"q": q.strip(), "q_enc": "UTF-8", "target": "stock"}
    headers = {
        "Referer": "https://finance.naver.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        # 응답 구조: {"items": [{"code": "...", "name": "...", ...}, ...]}
        results = []
        for item in data.get("items", [])[:10]:
            code = item.get("code", "")
            name = item.get("name", "")
            if code and name:
                results.append({"name": name, "code": code})
        return results
    except Exception:
        return []


@router.get("/stocks/{code}/detail")
async def get_stock_detail(code: str):
    try:
        price, detail = await asyncio.gather(
            naver_client.get_stock_price(code),
            naver_client.get_stock_detail(code),
        )
        return {
            "code": price.code,
            "name": price.name,
            "current_price": price.current_price,
            "change_price": price.change_price,
            "change_rate": price.change_rate,
            "volume": price.volume,
            "high_price": price.high_price,
            "low_price": price.low_price,
            "open_price": price.open_price,
            "week52_high": detail.get("week52_high"),
            "week52_low": detail.get("week52_low"),
            "per": detail.get("per"),
            "pbr": detail.get("pbr"),
            "market_cap": detail.get("market_cap"),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stock detail: {e}")


@router.get("/stocks/{code}/history")
async def get_stock_history(code: str, count: int = 60):
    """종목 일봉 히스토리 조회 (기본 60일)"""
    try:
        data = await naver_client.get_stock_history(code, count=min(count, 250))
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stock history: {e}")


@router.get("/stocks/{code}", response_model=StockPrice)
async def get_stock(code: str):
    try:
        return await naver_client.get_stock_price(code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stock data: {e}")


@router.get("/indices", response_model=List[IndexPrice])
async def get_indices():
    now = time.monotonic()
    if _indices_cache["data"] is not None and now - _indices_cache["ts"] < _INDICES_TTL:
        return _indices_cache["data"]
    try:
        results = await asyncio.gather(
            _fetch_index("KOSPI"),
            _fetch_index("KOSDAQ"),
        )
        _indices_cache["data"] = list(results)
        _indices_cache["ts"] = time.monotonic()
        return _indices_cache["data"]
    except Exception as e:
        if _indices_cache["data"] is not None:
            # 수집 실패 — 마지막 정상값 유지 (헤더 지수바가 502로 깨지지 않게)
            return _indices_cache["data"]
        raise HTTPException(status_code=502, detail=f"Failed to fetch index data: {e}")
