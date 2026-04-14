from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Optional
import logging

from app.db import get_supabase
from app.brokers.mock_broker import mock_broker
from app.brokers.real_broker import real_broker
from app.services.historical_data import get_daily_close_prices
from app.services.naver_client import naver_client
from app.models.trading import TradingConfig, TradingSignal

logger = logging.getLogger(__name__)

_trading_ws_clients: set = set()

KST = timezone(timedelta(hours=9))


def register_trading_ws(ws) -> None:
    _trading_ws_clients.add(ws)


def unregister_trading_ws(ws) -> None:
    _trading_ws_clients.discard(ws)


async def _broadcast_signal(signal: TradingSignal) -> None:
    dead = set()
    for ws in _trading_ws_clients:
        try:
            await ws.send_json(signal.model_dump())
        except Exception:
            dead.add(ws)
    for ws in dead:
        _trading_ws_clients.discard(ws)


def _is_market_hours() -> bool:
    """장중 여부 확인 (KST 09:00 ~ 15:30, 월~금)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 주말
        return False
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def _get_config_sync() -> Optional[dict]:
    sb = get_supabase()
    res = sb.table("trading_config").select("*").limit(1).execute()
    return res.data[0] if res.data else None


def _get_watchlist_sync() -> list[dict]:
    sb = get_supabase()
    res = sb.table("watchlist").select("*").eq("is_active", True).execute()
    return res.data or []


def _get_positions_sync(mode: str) -> list[dict]:
    sb = get_supabase()
    res = sb.table("positions").select("*").eq("mode", mode).execute()
    return res.data or []


def _ensure_config_sync() -> dict:
    """trading_config 테이블에 초기 행이 없으면 생성"""
    import uuid
    sb = get_supabase()
    res = sb.table("trading_config").select("*").limit(1).execute()
    if not res.data:
        default = {
            "id": str(uuid.uuid4()),
            "short_ma": 5,
            "long_ma": 20,
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
            "paper_initial_capital": 10_000_000,
            "paper_balance": 10_000_000,
            "is_running": False,
        }
        sb.table("trading_config").insert(default).execute()
        return default
    return res.data[0]


def _update_config_sync(updates: dict) -> dict:
    sb = get_supabase()
    res = sb.table("trading_config").select("id").limit(1).execute()
    if not res.data:
        _ensure_config_sync()
        res = sb.table("trading_config").select("id").limit(1).execute()
    config_id = res.data[0]["id"]
    updated = sb.table("trading_config").update(updates).eq("id", config_id).execute()
    return updated.data[0] if updated.data else {}


def calc_ma(prices: list[int], period: int) -> float:
    """최근 period일 이동평균 계산"""
    if len(prices) < period:
        return 0.0
    return mean(prices[:period])


def detect_signal(prices: list[int], short: int = 5, long: int = 20) -> Optional[str]:
    """골든/데드크로스 감지.

    Args:
        prices: 최신→과거 순 종가 리스트 (최소 long+1개 필요)
    Returns:
        "BUY" (골든크로스), "SELL" (데드크로스), None (시그널 없음)
    """
    if len(prices) < long + 1:
        return None

    # 오늘 MA
    ma_short_today = calc_ma(prices, short)
    ma_long_today = calc_ma(prices, long)

    # 어제 MA (인덱스 1부터)
    ma_short_prev = calc_ma(prices[1:], short)
    ma_long_prev = calc_ma(prices[1:], long)

    # 골든크로스: 어제까지 단기 <= 장기, 오늘 단기 > 장기
    if ma_short_prev <= ma_long_prev and ma_short_today > ma_long_today:
        return "BUY"

    # 데드크로스: 어제까지 단기 >= 장기, 오늘 단기 < 장기
    if ma_short_prev >= ma_long_prev and ma_short_today < ma_long_today:
        return "SELL"

    return None


async def _process_stock_signal(
    stock_code: str,
    stock_name: str,
    config: dict,
    mode: str,
) -> None:
    """개별 종목 시그널 처리"""
    broker = mock_broker if mode == "paper" else real_broker

    try:
        prices = await get_daily_close_prices(stock_code, count=config["long_ma"] + 2)
        if not prices:
            return

        signal = detect_signal(prices, short=config["short_ma"], long=config["long_ma"])
        if not signal:
            return

        # 현재가 조회
        stock = await naver_client.get_stock_price(stock_code)
        current_price = stock.current_price
        if current_price <= 0:
            return

        # 포지션 확인
        positions = await asyncio.to_thread(_get_positions_sync, mode)
        has_position = any(p["stock_code"] == stock_code for p in positions)

        if signal == "BUY" and not has_position:
            # 잔고의 10%로 매수 수량 계산
            balance = await broker.get_balance()
            invest_amount = int(balance * 0.10)
            quantity = invest_amount // current_price
            if quantity <= 0:
                return

            stop_loss_price = int(current_price * (1 - config["stop_loss_pct"] / 100))
            take_profit_price = int(current_price * (1 + config["take_profit_pct"] / 100))

            result = await broker.buy(
                stock_code, stock_name, current_price, quantity,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                reason="golden_cross",
            )

            if result["success"]:
                await _broadcast_signal(TradingSignal(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    signal_type="BUY",
                    price=current_price,
                    quantity=quantity,
                    reason="golden_cross",
                    mode=mode,
                    message=result["message"],
                    timestamp=datetime.now().isoformat(),
                ))

        elif signal == "SELL" and has_position:
            position = next(p for p in positions if p["stock_code"] == stock_code)
            result = await broker.sell(
                stock_code, stock_name, current_price, position["quantity"],
                reason="dead_cross",
            )

            if result["success"]:
                await _broadcast_signal(TradingSignal(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    signal_type="SELL",
                    price=current_price,
                    quantity=position["quantity"],
                    reason="dead_cross",
                    mode=mode,
                    message=result["message"],
                    timestamp=datetime.now().isoformat(),
                ))

    except Exception as e:
        logger.warning(f"[TradingEngine] {stock_code} 처리 중 오류: {e}")


async def _check_stop_take(config: dict, mode: str) -> None:
    """손절/익절 체크"""
    broker = mock_broker if mode == "paper" else real_broker
    positions = await asyncio.to_thread(_get_positions_sync, mode)

    for position in positions:
        try:
            stock = await naver_client.get_stock_price(position["stock_code"])
            current_price = stock.current_price

            reason = None
            if current_price <= position["stop_loss_price"]:
                reason = "stop_loss"
            elif current_price >= position["take_profit_price"]:
                reason = "take_profit"

            if reason:
                result = await broker.sell(
                    position["stock_code"], position["stock_name"],
                    current_price, position["quantity"],
                    reason=reason,
                )
                if result["success"]:
                    await _broadcast_signal(TradingSignal(
                        stock_code=position["stock_code"],
                        stock_name=position["stock_name"],
                        signal_type="SELL",
                        price=current_price,
                        quantity=position["quantity"],
                        reason=reason,
                        mode=mode,
                        message=result["message"],
                        timestamp=datetime.now().isoformat(),
                    ))
        except Exception as e:
            logger.warning(f"[TradingEngine] 손절/익절 체크 오류 {position['stock_code']}: {e}")


async def run_trading_cycle() -> None:
    """매매 사이클 실행 (APScheduler에서 1분마다 호출)"""
    try:
        config = await asyncio.to_thread(_get_config_sync)
        if not config or not config.get("is_running"):
            return

        watchlist = await asyncio.to_thread(_get_watchlist_sync)
        if not watchlist:
            return

        modes = ["paper"]
        # 실거래는 장중에만 실행
        if _is_market_hours():
            modes.append("real")

        for mode in modes:
            # 손절/익절 먼저 체크
            await _check_stop_take(config, mode)

            # 골든/데드크로스 시그널 체크
            tasks = [
                _process_stock_signal(item["stock_code"], item["stock_name"], config, mode)
                for item in watchlist
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.error(f"[TradingEngine] 사이클 오류: {e}")


async def get_config() -> TradingConfig:
    config = await asyncio.to_thread(_ensure_config_sync)
    return TradingConfig(**config)


async def update_config(updates: dict) -> TradingConfig:
    config = await asyncio.to_thread(_update_config_sync, updates)
    # Re-fetch to get full row
    full = await asyncio.to_thread(_get_config_sync)
    return TradingConfig(**full)


async def toggle_engine(is_running: bool) -> TradingConfig:
    return await update_config({"is_running": is_running})
