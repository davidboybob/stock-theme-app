from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.db import get_supabase
from app.services.historical_data import get_daily_close_prices

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

"""
필요한 Supabase 테이블:

CREATE TABLE daily_price_snapshot (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  stock_name TEXT NOT NULL,
  close_price BIGINT NOT NULL,
  recorded_at DATE NOT NULL,
  UNIQUE (stock_code, recorded_at)
);
"""


def _is_trading_day() -> bool:
    """오늘이 거래일(월~금)인지 확인"""
    now = datetime.now(KST)
    return now.weekday() < 5  # 0=월, 4=금


def _get_watchlist_sync() -> list[dict]:
    sb = get_supabase()
    res = sb.table("watchlist").select("stock_code, stock_name").eq("is_active", True).execute()
    return res.data or []


def _save_snapshot_sync(stock_code: str, stock_name: str, close_price: int, recorded_at: str) -> None:
    sb = get_supabase()
    # 같은 날짜 중복 저장 방지: upsert 패턴
    sb.table("daily_price_snapshot").upsert({
        "stock_code": stock_code,
        "stock_name": stock_name,
        "close_price": close_price,
        "recorded_at": recorded_at,
    }, on_conflict="stock_code,recorded_at").execute()


async def _snapshot_stock(stock_code: str, stock_name: str, date_str: str) -> None:
    """개별 종목 종가 저장"""
    try:
        prices = await get_daily_close_prices(stock_code, count=1)
        if not prices:
            logger.warning(f"[Snapshot] 종가 없음: {stock_code}")
            return
        close_price = prices[0]
        await asyncio.to_thread(_save_snapshot_sync, stock_code, stock_name, close_price, date_str)
        logger.info(f"[Snapshot] {stock_name}({stock_code}) 종가 저장: {close_price:,}원")
    except Exception as e:
        logger.warning(f"[Snapshot] {stock_code} 저장 실패: {e}")


async def run_daily_snapshot() -> None:
    """
    장 마감 후 감시 종목 전체 종가 스냅샷 저장.
    APScheduler에서 매일 16:10 KST에 호출.
    """
    if not _is_trading_day():
        logger.info("[Snapshot] 오늘은 거래일이 아닙니다. 스냅샷 건너뜀.")
        return

    now = datetime.now(KST)
    date_str = now.strftime("%Y-%m-%d")
    logger.info(f"[Snapshot] {date_str} 일봉 스냅샷 시작")

    try:
        watchlist = await asyncio.to_thread(_get_watchlist_sync)
        if not watchlist:
            logger.info("[Snapshot] 감시 종목 없음. 종료.")
            return

        tasks = [
            _snapshot_stock(item["stock_code"], item["stock_name"], date_str)
            for item in watchlist
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"[Snapshot] {len(watchlist)}개 종목 스냅샷 완료")
    except Exception as e:
        logger.error(f"[Snapshot] 스냅샷 오류: {e}")
