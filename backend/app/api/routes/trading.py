from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List

from app.db import get_supabase
from app.models.trading import (
    WatchlistItem, WatchlistAdd,
    TradingConfig, TradingConfigUpdate,
    Position, TradeHistory,
)
from app.services.trading_engine import (
    get_config, update_config, toggle_engine,
    register_trading_ws, unregister_trading_ws,
)

router = APIRouter(tags=["trading"])


# ─── Config ───────────────────────────────────────────────────────────────────

@router.get("/trading/config", response_model=TradingConfig)
async def get_trading_config():
    return await get_config()


@router.put("/trading/config", response_model=TradingConfig)
async def update_trading_config(body: TradingConfigUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "변경할 설정이 없습니다")
    return await update_config(updates)


@router.post("/trading/config/toggle", response_model=TradingConfig)
async def toggle_trading_engine(body: dict):
    is_running = body.get("is_running", False)
    return await toggle_engine(bool(is_running))


@router.post("/trading/config/reset-balance", response_model=TradingConfig)
async def reset_paper_balance():
    """모의투자 잔고를 초기 자금으로 리셋"""
    config = await get_config()
    return await update_config({"paper_balance": config.paper_initial_capital})


# ─── Watchlist ────────────────────────────────────────────────────────────────

def _db_get_watchlist() -> list:
    sb = get_supabase()
    res = sb.table("watchlist").select("*").order("added_at", desc=True).execute()
    return res.data or []


def _db_add_watchlist(item: WatchlistAdd) -> dict:
    sb = get_supabase()
    row = {
        "id": str(uuid.uuid4()),
        "stock_code": item.stock_code,
        "stock_name": item.stock_name,
        "theme_id": item.theme_id,
        "is_active": True,
        "added_at": datetime.now().isoformat(),
    }
    res = sb.table("watchlist").insert(row).execute()
    return res.data[0] if res.data else row


def _db_delete_watchlist(item_id: str) -> bool:
    sb = get_supabase()
    res = sb.table("watchlist").delete().eq("id", item_id).execute()
    return len(res.data or []) > 0


@router.get("/trading/watchlist", response_model=List[WatchlistItem])
async def get_watchlist():
    return await asyncio.to_thread(_db_get_watchlist)


@router.post("/trading/watchlist", response_model=WatchlistItem)
async def add_to_watchlist(body: WatchlistAdd):
    # 중복 체크
    existing = await asyncio.to_thread(_db_get_watchlist)
    if any(w["stock_code"] == body.stock_code for w in existing):
        raise HTTPException(409, f"이미 감시 목록에 있는 종목입니다: {body.stock_code}")
    return await asyncio.to_thread(_db_add_watchlist, body)


@router.delete("/trading/watchlist/{item_id}")
async def remove_from_watchlist(item_id: str):
    deleted = await asyncio.to_thread(_db_delete_watchlist, item_id)
    if not deleted:
        raise HTTPException(404, "감시 종목을 찾을 수 없습니다")
    return {"ok": True}


# ─── Positions ────────────────────────────────────────────────────────────────

def _db_get_positions() -> list:
    sb = get_supabase()
    res = sb.table("positions").select("*").order("entered_at", desc=True).execute()
    return res.data or []


@router.get("/trading/positions", response_model=List[Position])
async def get_positions():
    return await asyncio.to_thread(_db_get_positions)


# ─── Trade History ────────────────────────────────────────────────────────────

def _db_get_history(limit: int = 100) -> list:
    sb = get_supabase()
    res = sb.table("trade_history").select("*").order("executed_at", desc=True).limit(limit).execute()
    return res.data or []


@router.get("/trading/history", response_model=List[TradeHistory])
async def get_trade_history(limit: int = 100):
    return await asyncio.to_thread(_db_get_history, limit)


# ─── WebSocket ────────────────────────────────────────────────────────────────

@router.websocket("/ws/trading")
async def trading_websocket(websocket: WebSocket):
    await websocket.accept()
    register_trading_ws(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unregister_trading_ws(websocket)
