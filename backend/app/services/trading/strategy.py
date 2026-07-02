"""Strategy 인터페이스 — 시장 상태를 평가해 매매 시그널을 낸다."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.models.bot import TradeSignal


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    async def generate_signals(self) -> List[TradeSignal]:
        """BUY/SELL 시그널 목록을 반환한다 (없으면 빈 리스트)."""
        raise NotImplementedError
