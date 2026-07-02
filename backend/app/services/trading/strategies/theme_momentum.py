"""테마 모멘텀 전략.

기존 테마 강도(60초 캐시)를 그대로 입력으로 사용한다:
- 테마 평균 등락률 >= threshold 이고 상승 종목 비율 >= 60% 이면
  테마 내 등락률 1위 종목에 BUY 시그널
- 같은 종목은 쿨다운(기본 60분) 내 재시그널 금지
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.models.bot import TradeSignal
from app.services.theme_service import get_all_theme_strengths, get_theme_detail
from app.services.trading.strategy import Strategy


class ThemeMomentumStrategy(Strategy):
    name = "theme_momentum"

    def __init__(self, threshold: Optional[float] = None, cooldown_minutes: int = 60):
        self.threshold = (
            threshold if threshold is not None else get_settings().bot_theme_threshold
        )
        self.cooldown_seconds = cooldown_minutes * 60
        self._last_signal_at: Dict[str, float] = {}

    def _in_cooldown(self, symbol: str) -> bool:
        ts = self._last_signal_at.get(symbol)
        return ts is not None and (time.monotonic() - ts) < self.cooldown_seconds

    async def generate_signals(self) -> List[TradeSignal]:
        signals: List[TradeSignal] = []
        for st in await get_all_theme_strengths():
            if st.avg_change_rate < self.threshold:
                continue
            if not st.total or (st.rising_count / st.total) < 0.6:
                continue

            detail = await get_theme_detail(st.theme_id)
            if not detail or not detail.stock_prices:
                continue

            top = max(detail.stock_prices, key=lambda p: p.change_rate)
            if self._in_cooldown(top.code):
                continue
            self._last_signal_at[top.code] = time.monotonic()

            signals.append(
                TradeSignal(
                    strategy=self.name,
                    action="BUY",
                    symbol=top.code,
                    symbol_name=top.name,
                    theme_id=st.theme_id,
                    theme_name=st.theme_name,
                    price=top.current_price,
                    reason=(
                        f"테마 '{st.theme_name}' 평균 {st.avg_change_rate:+.2f}% "
                        f"(임계 {self.threshold:+.1f}%), 상승 {st.rising_count}/{st.total} "
                        f"— 대표종목 {top.name} {top.change_rate:+.2f}%"
                    ),
                )
            )
        return signals
