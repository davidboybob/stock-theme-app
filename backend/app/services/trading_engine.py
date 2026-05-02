from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Optional, List
import logging

from app.db import get_supabase
from app.brokers.mock_broker import mock_broker
from app.brokers.real_broker import real_broker
from app.services.historical_data import get_daily_close_prices
from app.services.naver_client import naver_client
from app.models.trading import TradingConfig, TradingSignal

logger = logging.getLogger(__name__)

_trading_ws_clients: set = set()

_stock_locks: dict[str, asyncio.Lock] = {}


def _get_stock_lock(code: str) -> asyncio.Lock:
    if code not in _stock_locks:
        _stock_locks[code] = asyncio.Lock()
    return _stock_locks[code]

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
            "strategy": "ma_cross",
            "rsi_period": 14,
            "rsi_oversold": 30.0,
            "rsi_overbought": 70.0,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
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


def _calc_ema(values: List[float], period: int) -> List[float]:
    """EMA 계산 (오래된→최신 순 입력)"""
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    ema = [mean(values[:period])]
    for v in values[period:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema


def calc_rsi(prices: list[int], period: int = 14) -> float:
    """RSI 계산. prices: 최신→과거 순 (최소 period+1개 필요)"""
    if len(prices) < period + 1:
        return 50.0
    # 오래된→최신 순 변환 후 변화량 계산
    ordered = list(reversed(prices[:period + 1]))
    gains, losses = [], []
    for i in range(1, len(ordered)):
        change = ordered[i] - ordered[i - 1]
        gains.append(max(0.0, float(change)))
        losses.append(max(0.0, float(-change)))
    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_macd(
    prices: list[int],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float]:
    """MACD 계산. Returns (macd_line, signal_line). prices: 최신→과거 순"""
    min_required = slow + signal_period
    if len(prices) < min_required:
        return 0.0, 0.0
    ordered = [float(p) for p in reversed(prices)]
    fast_ema = _calc_ema(ordered, fast)
    slow_ema = _calc_ema(ordered, slow)
    if not fast_ema or not slow_ema:
        return 0.0, 0.0
    # fast_ema[i + offset] aligns with slow_ema[i] (both start from slow-1 index)
    offset = slow - fast
    macd_line = [fast_ema[i + offset] - slow_ema[i] for i in range(len(slow_ema))]
    if len(macd_line) < signal_period:
        return 0.0, 0.0
    sig_ema = _calc_ema(macd_line, signal_period)
    if not sig_ema:
        return 0.0, 0.0
    return macd_line[-1], sig_ema[-1]


def _detect_ma_cross(prices: list[int], short: int, long: int) -> Optional[str]:
    if len(prices) < long + 1:
        return None
    ma_short_today = calc_ma(prices, short)
    ma_long_today = calc_ma(prices, long)
    ma_short_prev = calc_ma(prices[1:], short)
    ma_long_prev = calc_ma(prices[1:], long)
    if ma_short_prev <= ma_long_prev and ma_short_today > ma_long_today:
        return "BUY"
    if ma_short_prev >= ma_long_prev and ma_short_today < ma_long_today:
        return "SELL"
    return None


def _detect_rsi_signal(
    prices: list[int],
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> Optional[str]:
    rsi = calc_rsi(prices, period)
    if rsi <= oversold:
        return "BUY"
    if rsi >= overbought:
        return "SELL"
    return None


def _detect_macd_signal(
    prices: list[int],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> Optional[str]:
    if len(prices) < slow + signal_period + 1:
        return None
    macd_today, sig_today = calc_macd(prices, fast, slow, signal_period)
    macd_prev, sig_prev = calc_macd(prices[1:], fast, slow, signal_period)
    if macd_prev <= sig_prev and macd_today > sig_today:
        return "BUY"
    if macd_prev >= sig_prev and macd_today < sig_today:
        return "SELL"
    return None


def detect_signal(
    prices: list[int],
    short: int = 5,
    long: int = 20,
    strategy: str = "ma_cross",
    rsi_period: int = 14,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> Optional[str]:
    """전략에 따른 매매 시그널 감지. prices: 최신→과거 순"""
    if strategy == "rsi":
        return _detect_rsi_signal(prices, rsi_period, rsi_oversold, rsi_overbought)
    if strategy == "macd":
        return _detect_macd_signal(prices, macd_fast, macd_slow, macd_signal)
    return _detect_ma_cross(prices, short, long)


async def _process_stock_signal(
    stock_code: str,
    stock_name: str,
    config: dict,
    mode: str,
) -> None:
    """개별 종목 시그널 처리"""
    async with _get_stock_lock(stock_code):
        broker = mock_broker if mode == "paper" else real_broker

        try:
            # 전략별 최소 필요 데이터 수 계산
            strategy = config.get("strategy", "ma_cross")
            if strategy == "macd":
                needed = config.get("macd_slow", 26) + config.get("macd_signal", 9) + 2
            elif strategy == "rsi":
                needed = config.get("rsi_period", 14) + 2
            else:
                needed = config.get("long_ma", 20) + 2
            prices = await get_daily_close_prices(stock_code, count=needed)
            if not prices:
                return

            signal = detect_signal(
                prices,
                short=config.get("short_ma", 5),
                long=config.get("long_ma", 20),
                strategy=config.get("strategy", "ma_cross"),
                rsi_period=config.get("rsi_period", 14),
                rsi_oversold=config.get("rsi_oversold", 30.0),
                rsi_overbought=config.get("rsi_overbought", 70.0),
                macd_fast=config.get("macd_fast", 12),
                macd_slow=config.get("macd_slow", 26),
                macd_signal=config.get("macd_signal", 9),
            )
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
