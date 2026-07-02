"""자동매매 봇 제어 라우트.

TRADING_ENABLED=true 일 때만 main.py 에서 라우터가 등록된다.
실주문 전환(dry_run=false)은 BOT_LIVE_TRADING=true 환경변수가 함께 필요하다.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.models.bot import BotModeIn, BotStartIn, BotStatus, TradeSignal
from app.services.trading.engine import get_bot_engine

router = APIRouter(prefix="/trading", tags=["trading"])


@router.get("/status", response_model=BotStatus)
async def get_status():
    return await get_bot_engine().status()


@router.post("/start", response_model=BotStatus)
async def start_bot(body: BotStartIn):
    engine = get_bot_engine()
    engine.start(
        account_seq=body.account_seq,
        interval_minutes=body.interval_minutes,
        threshold=body.threshold,
    )
    return await engine.status()


@router.post("/stop", response_model=BotStatus)
async def stop_bot():
    engine = get_bot_engine()
    engine.stop()
    return await engine.status()


@router.post("/mode", response_model=BotStatus)
async def set_mode(body: BotModeIn):
    engine = get_bot_engine()
    if not body.dry_run and not get_settings().bot_live_trading:
        raise HTTPException(
            status_code=403,
            detail="실주문 모드는 BOT_LIVE_TRADING=true 환경변수가 필요합니다 (dry-run 강제 중)",
        )
    engine.dry_run = body.dry_run
    return await engine.status()


@router.get("/signals", response_model=List[TradeSignal])
async def get_signals(limit: int = Query(50, ge=1, le=200)):
    return get_bot_engine().signals(limit)
