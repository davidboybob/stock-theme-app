"""자동매매 안전장치 (Phase 4).

주문 실행 전 리스크 체크와 kill switch를 담당한다.
dry-run에서도 체크를 수행해 시그널에 차단 사유를 남긴다 —
실전 전환 전에 한도 설정이 적절한지 dry-run 데이터로 검증하기 위함.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.core.config import get_settings

KST = timezone(timedelta(hours=9))


class RiskManager:
    def __init__(self):
        self.kill_switch = False
        self.kill_reason: Optional[str] = None
        self.consecutive_failures = 0
        self._daily_order_amount = 0
        self._daily_blocked = 0
        self._day: Optional[date] = None

    def _roll_day(self) -> None:
        today = datetime.now(KST).date()
        if self._day != today:
            self._day = today
            self._daily_order_amount = 0
            self._daily_blocked = 0
            self.consecutive_failures = 0

    # ── kill switch ────────────────────────────────────

    def activate_kill_switch(self, reason: str) -> None:
        self.kill_switch = True
        self.kill_reason = reason

    def release_kill_switch(self) -> None:
        self.kill_switch = False
        self.kill_reason = None
        self.consecutive_failures = 0

    # ── 주문 전 체크 ────────────────────────────────────

    def check_order(self, price: Optional[int], quantity: int) -> Optional[str]:
        """주문 가능하면 None, 불가면 차단 사유를 반환한다."""
        self._roll_day()
        settings = get_settings()

        if self.kill_switch:
            return f"kill switch 활성 ({self.kill_reason})"

        amount = (price or 0) * quantity
        if amount <= 0:
            return "가격 정보 없음 — 주문 금액 산출 불가"
        if amount > settings.bot_max_order_amount:
            return (
                f"건당 상한 초과 ({amount:,}원 > {settings.bot_max_order_amount:,}원)"
            )
        if self._daily_order_amount + amount > settings.bot_daily_max_order_amount:
            return (
                f"일일 상한 초과 (누적 {self._daily_order_amount:,}원 + {amount:,}원 "
                f"> {settings.bot_daily_max_order_amount:,}원)"
            )
        return None

    def record_blocked(self) -> None:
        self._roll_day()
        self._daily_blocked += 1

    # ── 주문 결과 반영 ──────────────────────────────────

    def record_order_success(self, price: Optional[int], quantity: int) -> None:
        self._roll_day()
        self._daily_order_amount += (price or 0) * quantity
        self.consecutive_failures = 0

    def record_order_failure(self) -> Optional[str]:
        """실패 누적. 연속 실패 한도 도달 시 kill switch를 올리고 사유를 반환한다."""
        self._roll_day()
        self.consecutive_failures += 1
        limit = get_settings().bot_max_consecutive_failures
        if self.consecutive_failures >= limit:
            reason = f"연속 주문 실패 {self.consecutive_failures}회 — 자동 정지"
            self.activate_kill_switch(reason)
            return reason
        return None

    # ── 일 손실 한도 (live 전용, 계좌 손익 기반) ─────────

    def check_daily_loss(self, daily_profit_loss: float) -> Optional[str]:
        limit = get_settings().bot_daily_loss_limit
        if daily_profit_loss <= -limit:
            reason = f"일 손실 한도 초과 ({daily_profit_loss:+,.0f}원 ≤ -{limit:,}원)"
            self.activate_kill_switch(reason)
            return reason
        return None

    # ── 상태 ───────────────────────────────────────────

    def snapshot(self) -> dict:
        self._roll_day()
        settings = get_settings()
        return {
            "kill_switch": self.kill_switch,
            "kill_reason": self.kill_reason,
            "consecutive_failures": self.consecutive_failures,
            "daily_order_amount": self._daily_order_amount,
            "daily_max_order_amount": settings.bot_daily_max_order_amount,
            "max_order_amount": settings.bot_max_order_amount,
            "daily_loss_limit": settings.bot_daily_loss_limit,
            "blocked_today": self._daily_blocked,
        }
