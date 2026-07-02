"""자동매매 봇 엔진.

- APScheduler 주기 실행 (기본 5분)
- 장운영시간 체크: 토스 market-calendar의 오늘 정규장 창(1일 캐시),
  조회 실패 시 평일 09:00~15:30 휴리스틱
- dry-run 기본: 시그널을 기록만 하고 주문하지 않는다
- live 전환은 BOT_LIVE_TRADING=true 환경변수 + 런타임 토글이 모두 필요
"""
from __future__ import annotations

import warnings
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db import get_supabase
from app.models.bot import BotStatus, TradeSignal
from app.models.trading import OrderCreateIn
from app.services import order_service
from app.services.toss_client import get_toss_client
from app.services.trading.strategies.theme_momentum import ThemeMomentumStrategy

KST = timezone(timedelta(hours=9))
_MAX_MEMORY_SIGNALS = 200


def _sb_insert(table: str, entry: dict) -> None:
    """Supabase 기록. 실패해도 봇 흐름을 막지 않는다 (프로젝트 정지 시에도 동작)."""
    try:
        get_supabase().table(table).insert(entry).execute()
    except Exception as e:
        warnings.warn(f"{table} 기록 실패: {e}")


class BotEngine:
    def __init__(self):
        settings = get_settings()
        self._scheduler: Optional[AsyncIOScheduler] = None
        self.strategy = ThemeMomentumStrategy()
        self.dry_run = True
        self.interval_minutes = settings.bot_interval_minutes
        self.account_seq: Optional[int] = None
        self.last_run_at: Optional[str] = None
        self.last_run_result: Optional[str] = None
        self._signals: List[TradeSignal] = []
        self._signals_today = 0
        self._signals_today_date: Optional[date] = None
        # 오늘 정규장 (start, end) — 날짜 단위 캐시
        self._market_cache: dict = {"date": None, "window": None}

    # ── 장운영시간 ──────────────────────────────────────

    async def _market_window(self) -> Optional[Tuple[datetime, datetime]]:
        today = datetime.now(KST).date()
        if self._market_cache["date"] == today:
            return self._market_cache["window"]

        window: Optional[Tuple[datetime, datetime]] = None
        try:
            cal = await get_toss_client().get_kr_market_calendar()
            reg = (((cal or {}).get("today") or {}).get("integrated") or {}).get(
                "regularMarket"
            ) or {}
            # 휴장일에는 regularMarket 창이 없다 → window=None(하루 종일 닫힘)
            if reg.get("startTime") and reg.get("endTime"):
                window = (
                    datetime.fromisoformat(reg["startTime"]),
                    datetime.fromisoformat(reg["endTime"]),
                )
        except Exception as e:
            warnings.warn(f"장운영 캘린더 조회 실패, 평일 09:00~15:30 휴리스틱 사용: {e}")
            now = datetime.now(KST)
            if now.weekday() < 5:
                window = (
                    now.replace(hour=9, minute=0, second=0, microsecond=0),
                    now.replace(hour=15, minute=30, second=0, microsecond=0),
                )

        self._market_cache = {"date": today, "window": window}
        return window

    async def is_market_open(self) -> bool:
        window = await self._market_window()
        if not window:
            return False
        now = datetime.now(KST)
        return window[0] <= now <= window[1]

    # ── 실행 사이클 ─────────────────────────────────────

    def _roll_daily_counter(self) -> None:
        today = datetime.now(KST).date()
        if self._signals_today_date != today:
            self._signals_today_date = today
            self._signals_today = 0

    async def run_once(self) -> None:
        settings = get_settings()
        self.last_run_at = datetime.now(KST).isoformat()
        try:
            if not await self.is_market_open():
                self.last_run_result = "장 운영시간 아님 — 스킵"
                return

            self._roll_daily_counter()
            if self._signals_today >= settings.bot_max_signals_per_day:
                self.last_run_result = (
                    f"일일 시그널 한도({settings.bot_max_signals_per_day}) 도달 — 스킵"
                )
                return

            signals = await self.strategy.generate_signals()
            for sig in signals:
                await self._handle_signal(sig)
            self.last_run_result = f"시그널 {len(signals)}건"
        except Exception as e:
            self.last_run_result = f"오류: {e}"
            warnings.warn(f"봇 실행 오류: {e}")

    async def _handle_signal(self, sig: TradeSignal) -> None:
        settings = get_settings()
        sig.dry_run = self.dry_run or not settings.bot_live_trading
        if sig.price:
            sig.quantity = max(settings.bot_order_budget // sig.price, 1)

        if not sig.dry_run:
            await self._execute_order(sig)

        self._signals.append(sig)
        del self._signals[:-_MAX_MEMORY_SIGNALS]
        self._signals_today += 1
        _sb_insert("trade_signals", sig.model_dump())

    async def _execute_order(self, sig: TradeSignal) -> None:
        """live 모드 주문 실행 — 지정가만 사용(시장가 슬리피지 방지)."""
        if not self.account_seq:
            sig.error = "account_seq 미설정 — 주문 불가"
            return
        try:
            order = OrderCreateIn(
                symbol=sig.symbol,
                side=sig.action,
                order_type="LIMIT",
                quantity=sig.quantity,
                price=sig.price,
            )
            parsed = await order_service.create_order(
                self.account_seq, order, source="bot"
            )
            sig.executed = True
            sig.order_id = parsed.order_id
        except Exception as e:
            sig.error = str(e)[:300]

    # ── 제어 ───────────────────────────────────────────

    def start(
        self,
        account_seq: Optional[int] = None,
        interval_minutes: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> None:
        if self._scheduler:
            return
        if account_seq is not None:
            self.account_seq = account_seq
        if interval_minutes:
            self.interval_minutes = max(1, interval_minutes)
        if threshold is not None:
            self.strategy.threshold = threshold

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.run_once,
            "interval",
            minutes=self.interval_minutes,
            id="trading_bot",
            next_run_time=datetime.now(KST),  # 시작 즉시 1회 실행
        )
        self._scheduler.start()
        _sb_insert(
            "bot_runs",
            {
                "event": "START",
                "dry_run": self.dry_run or not get_settings().bot_live_trading,
                "interval_minutes": self.interval_minutes,
                "threshold": self.strategy.threshold,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def stop(self) -> None:
        if not self._scheduler:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        _sb_insert(
            "bot_runs",
            {"event": "STOP", "created_at": datetime.now(timezone.utc).isoformat()},
        )

    @property
    def running(self) -> bool:
        return self._scheduler is not None

    def signals(self, limit: int = 50) -> List[TradeSignal]:
        return list(reversed(self._signals[-limit:]))

    async def status(self) -> BotStatus:
        settings = get_settings()
        self._roll_daily_counter()
        return BotStatus(
            running=self.running,
            dry_run=self.dry_run or not settings.bot_live_trading,
            live_allowed=settings.bot_live_trading,
            interval_minutes=self.interval_minutes,
            threshold=self.strategy.threshold,
            market_open=await self.is_market_open(),
            account_seq=self.account_seq,
            last_run_at=self.last_run_at,
            last_run_result=self.last_run_result,
            signals_today=self._signals_today,
            max_signals_per_day=settings.bot_max_signals_per_day,
        )


_engine: Optional[BotEngine] = None


def get_bot_engine() -> BotEngine:
    global _engine
    if _engine is None:
        _engine = BotEngine()
    return _engine
