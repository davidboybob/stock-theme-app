import asyncio
import httpx
from fastapi import APIRouter, HTTPException
from typing import List
from app.models.stock import StockPrice, IndexPrice
from app.services.naver_client import naver_client

router = APIRouter(tags=["stocks"])


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


@router.get("/stocks/{code}", response_model=StockPrice)
async def get_stock(code: str):
    try:
        return await naver_client.get_stock_price(code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stock data: {e}")


@router.get("/indices", response_model=List[IndexPrice])
async def get_indices():
    try:
        results = await asyncio.gather(
            naver_client.get_index_price("KOSPI"),
            naver_client.get_index_price("KOSDAQ"),
        )
        return list(results)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch index data: {e}")
