"""자동매매 봇 모델."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeSignal(BaseModel):
    strategy: str
    action: str  # BUY / SELL
    symbol: str
    symbol_name: str = ""
    theme_id: str = ""
    theme_name: str = ""
    price: Optional[int] = None      # 시그널 시점 현재가
    quantity: int = 0                # 주문 예산 기준 산출 수량
    reason: str = ""
    dry_run: bool = True
    executed: bool = False           # live 주문 실행 여부
    order_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


class BotStatus(BaseModel):
    running: bool
    dry_run: bool
    live_allowed: bool               # BOT_LIVE_TRADING 환경변수
    interval_minutes: int
    threshold: float
    market_open: bool
    account_seq: Optional[int] = None
    last_run_at: Optional[str] = None
    last_run_result: Optional[str] = None
    signals_today: int = 0
    max_signals_per_day: int = 0


class BotStartIn(BaseModel):
    account_seq: Optional[int] = None       # live 주문에만 필요
    interval_minutes: Optional[int] = None
    threshold: Optional[float] = None


class BotModeIn(BaseModel):
    dry_run: bool
