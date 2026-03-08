import asyncio
from fastapi import APIRouter, HTTPException
from typing import List
from app.models.stock import StockPrice, IndexPrice
from app.services.naver_client import naver_client

router = APIRouter(tags=["stocks"])


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
