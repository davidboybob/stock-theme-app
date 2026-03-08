from fastapi import APIRouter, HTTPException
from typing import List
from app.models.stock import StockPrice, IndexPrice
from app.services.kis_client import kis_client

router = APIRouter(tags=["stocks"])


@router.get("/stocks/{code}", response_model=StockPrice)
async def get_stock(code: str):
    try:
        return await kis_client.get_stock_price(code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stock data: {e}")


@router.get("/indices", response_model=List[IndexPrice])
async def get_indices():
    import asyncio
    try:
        results = await asyncio.gather(
            kis_client.get_index_price("0001"),
            kis_client.get_index_price("1001"),
        )
        return list(results)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch index data: {e}")
