from __future__ import annotations

import asyncio
from typing import List, Optional

from app.services.historical_data import get_daily_close_prices
from app.services.trading_engine import detect_signal
from app.models.trading import (
    BacktestRequest,
    BacktestResult,
    BacktestStockResult,
    BacktestTrade,
)


async def _backtest_single(
    stock_code: str,
    stock_name: str,
    req: BacktestRequest,
) -> BacktestStockResult:
    prices_newest_first = await get_daily_close_prices(stock_code, count=req.count)

    # 전략별 최소 필요 데이터 수
    if req.strategy == "macd":
        min_window = req.macd_slow + req.macd_signal_period + 2
    elif req.strategy == "rsi":
        min_window = req.rsi_period + 2
    else:
        min_window = req.long_ma + 2

    empty_result = BacktestStockResult(
        stock_code=stock_code,
        stock_name=stock_name,
        strategy=req.strategy,
        initial_capital=req.initial_capital,
        final_balance=req.initial_capital,
        return_rate=0.0,
        win_rate=0.0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        max_drawdown=0.0,
        trades=[],
    )

    if not prices_newest_first or len(prices_newest_first) < min_window:
        return empty_result

    # 오래된→최신 순 변환
    prices_old_first = list(reversed(prices_newest_first))

    balance = req.initial_capital
    position: Optional[dict] = None  # {price, quantity, stop_loss, take_profit}
    trades: List[BacktestTrade] = []
    peak_value = req.initial_capital
    max_drawdown = 0.0
    winning = 0
    losing = 0
    trade_idx = 0

    for i in range(min_window, len(prices_old_first)):
        # 슬라이딩 윈도우: prices_old_first[0..i]를 최신→과거 순으로 변환
        window = list(reversed(prices_old_first[: i + 1]))
        current_price = prices_old_first[i]

        # 손절/익절 체크 (시그널보다 먼저)
        if position:
            hit_stop = current_price <= position["stop_loss"]
            hit_take = current_price >= position["take_profit"]
            if hit_stop or hit_take:
                reason = "stop_loss" if hit_stop else "take_profit"
                pnl = (current_price - position["price"]) * position["quantity"]
                balance += current_price * position["quantity"]
                trades.append(BacktestTrade(
                    index=trade_idx,
                    signal_type="SELL",
                    price=current_price,
                    quantity=position["quantity"],
                    reason=reason,
                    profit_loss=pnl,
                    balance_after=balance,
                ))
                trade_idx += 1
                winning += 1 if pnl >= 0 else 0
                losing += 1 if pnl < 0 else 0
                position = None

        # 시그널 감지
        signal = detect_signal(
            window,
            short=req.short_ma,
            long=req.long_ma,
            strategy=req.strategy,
            rsi_period=req.rsi_period,
            rsi_oversold=req.rsi_oversold,
            rsi_overbought=req.rsi_overbought,
            macd_fast=req.macd_fast,
            macd_slow=req.macd_slow,
            macd_signal=req.macd_signal_period,
        )

        if signal == "BUY" and not position:
            invest = int(balance * 0.10)
            quantity = invest // current_price
            if quantity <= 0:
                continue
            balance -= current_price * quantity
            position = {
                "price": current_price,
                "quantity": quantity,
                "stop_loss": int(current_price * (1 - req.stop_loss_pct / 100)),
                "take_profit": int(current_price * (1 + req.take_profit_pct / 100)),
            }
            trades.append(BacktestTrade(
                index=trade_idx,
                signal_type="BUY",
                price=current_price,
                quantity=quantity,
                reason=f"{req.strategy}_buy",
                balance_after=balance,
            ))
            trade_idx += 1

        elif signal == "SELL" and position:
            pnl = (current_price - position["price"]) * position["quantity"]
            balance += current_price * position["quantity"]
            trades.append(BacktestTrade(
                index=trade_idx,
                signal_type="SELL",
                price=current_price,
                quantity=position["quantity"],
                reason=f"{req.strategy}_sell",
                profit_loss=pnl,
                balance_after=balance,
            ))
            trade_idx += 1
            winning += 1 if pnl >= 0 else 0
            losing += 1 if pnl < 0 else 0
            position = None

        # 최고 자산 갱신 및 MDD 계산
        portfolio_value = balance + (current_price * position["quantity"] if position else 0)
        if portfolio_value > peak_value:
            peak_value = portfolio_value
        if peak_value > 0:
            drawdown = (peak_value - portfolio_value) / peak_value * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

    # 기간 종료 시 미청산 포지션 강제 청산
    if position:
        last_price = prices_old_first[-1]
        pnl = (last_price - position["price"]) * position["quantity"]
        balance += last_price * position["quantity"]
        trades.append(BacktestTrade(
            index=trade_idx,
            signal_type="SELL",
            price=last_price,
            quantity=position["quantity"],
            reason="period_end",
            profit_loss=pnl,
            balance_after=balance,
        ))
        winning += 1 if pnl >= 0 else 0
        losing += 1 if pnl < 0 else 0

    sell_count = winning + losing
    win_rate = (winning / sell_count * 100) if sell_count > 0 else 0.0
    return_rate = (balance - req.initial_capital) / req.initial_capital * 100

    return BacktestStockResult(
        stock_code=stock_code,
        stock_name=stock_name,
        strategy=req.strategy,
        initial_capital=req.initial_capital,
        final_balance=balance,
        return_rate=round(return_rate, 2),
        win_rate=round(win_rate, 2),
        total_trades=len(trades),
        winning_trades=winning,
        losing_trades=losing,
        max_drawdown=round(max_drawdown, 2),
        trades=trades,
    )


async def run_backtest(req: BacktestRequest) -> BacktestResult:
    """여러 종목 백테스팅 병렬 실행 및 합산 지표 계산"""
    names = req.stock_names or []
    tasks = [
        _backtest_single(
            code,
            names[i] if i < len(names) else code,
            req,
        )
        for i, code in enumerate(req.stock_codes)
    ]
    results = await asyncio.gather(*tasks)

    if not results:
        return BacktestResult(
            strategy=req.strategy,
            initial_capital=req.initial_capital,
            results=[],
            total_return_rate=0.0,
            avg_win_rate=0.0,
            avg_max_drawdown=0.0,
        )

    total_initial = req.initial_capital * len(results)
    total_final = sum(r.final_balance for r in results)
    total_return_rate = (total_final - total_initial) / total_initial * 100 if total_initial > 0 else 0.0
    avg_win_rate = sum(r.win_rate for r in results) / len(results)
    avg_max_drawdown = sum(r.max_drawdown for r in results) / len(results)

    return BacktestResult(
        strategy=req.strategy,
        initial_capital=req.initial_capital,
        results=list(results),
        total_return_rate=round(total_return_rate, 2),
        avg_win_rate=round(avg_win_rate, 2),
        avg_max_drawdown=round(avg_max_drawdown, 2),
    )
