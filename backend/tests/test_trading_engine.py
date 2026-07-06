"""자동매매 엔진 유닛 테스트"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.trading_engine import (
    calc_ma,
    detect_signal,
    _is_market_hours,
)


# ─── calc_ma ───────────────────────────────────────────────────────────────────

class TestCalcMa:
    def test_exact_period(self):
        prices = [100, 200, 300, 400, 500]
        assert calc_ma(prices, 5) == pytest.approx(300.0)

    def test_partial_period(self):
        # 요청 기간보다 데이터 적으면 0 반환
        prices = [100, 200]
        assert calc_ma(prices, 5) == 0.0

    def test_single_value(self):
        assert calc_ma([42], 1) == pytest.approx(42.0)

    def test_uses_first_n_prices(self):
        # 최신 5개만 사용 (인덱스 0~4)
        prices = [10, 20, 30, 40, 50, 999, 999, 999]
        assert calc_ma(prices, 5) == pytest.approx(30.0)  # (10+20+30+40+50)/5


# ─── detect_signal ─────────────────────────────────────────────────────────────

class TestDetectSignal:
    def _make_prices(self, short_today, long_today, short_prev, long_prev, padding_len=25):
        """
        detect_signal이 오늘/어제 MA를 계산하도록 가짜 가격 리스트 생성.
        실제 계산 대신 단순한 플랫 리스트를 사용 (MA=상수).
        """
        # 충분히 긴 리스트를 만든다 (long_ma+1 = 21개 필요)
        return [100] * padding_len

    def test_not_enough_data_returns_none(self):
        # 21개 미만이면 None
        prices = [100] * 20
        assert detect_signal(prices, short=5, long=20) is None

    def test_no_crossover_returns_none(self):
        # 모든 가격이 동일하면 크로스 없음
        prices = [100] * 25
        assert detect_signal(prices, short=5, long=20) is None

    def test_golden_cross_buy_signal(self):
        """
        어제: 5MA < 20MA  →  오늘: 5MA > 20MA  →  BUY
        최신 5개를 높게, 그 다음 20개를 낮게 세팅
        """
        # 오늘 5MA = 200, 장기 = 100이 되도록
        # 어제(인덱스 1~) 5MA < 20MA가 되도록
        prices = [200, 200, 200, 200, 200] + [100] * 20
        result = detect_signal(prices, short=5, long=20)
        assert result == "BUY"

    def test_dead_cross_sell_signal(self):
        """
        어제: 5MA > 20MA  →  오늘: 5MA < 20MA  →  SELL
        """
        prices = [50, 50, 50, 50, 50] + [200] * 20
        result = detect_signal(prices, short=5, long=20)
        assert result == "SELL"

    def test_already_crossed_no_signal(self):
        """이미 크로스 완료된 상태 → None (오늘도 어제도 같은 대소관계)"""
        # 5MA > 20MA 상태 유지 중 → 골든크로스 발생 안 함
        prices = [300, 300, 300, 300, 300, 200, 200, 200, 200, 200,
                  200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200]
        result = detect_signal(prices, short=5, long=20)
        assert result is None


# ─── _is_market_hours ──────────────────────────────────────────────────────────

KST = timezone(timedelta(hours=9))


class TestIsMarketHours:
    def _kst(self, weekday: int, hour: int, minute: int) -> datetime:
        """weekday: 0=월 ~ 6=일"""
        # 2026-04-13은 월요일 (weekday=0)
        base = datetime(2026, 4, 13, tzinfo=KST)
        delta = timedelta(days=weekday, hours=hour, minutes=minute)
        return base + delta

    @patch("app.services.trading_engine.datetime")
    def test_weekday_market_open(self, mock_dt):
        mock_dt.now.return_value = self._kst(0, 10, 0)  # 월요일 10:00
        assert _is_market_hours() is True

    @patch("app.services.trading_engine.datetime")
    def test_weekday_before_open(self, mock_dt):
        mock_dt.now.return_value = self._kst(0, 8, 59)  # 월요일 08:59
        assert _is_market_hours() is False

    @patch("app.services.trading_engine.datetime")
    def test_weekday_after_close(self, mock_dt):
        mock_dt.now.return_value = self._kst(0, 15, 31)  # 월요일 15:31
        assert _is_market_hours() is False

    @patch("app.services.trading_engine.datetime")
    def test_weekday_at_exact_open(self, mock_dt):
        mock_dt.now.return_value = self._kst(0, 9, 0)   # 월요일 09:00
        assert _is_market_hours() is True

    @patch("app.services.trading_engine.datetime")
    def test_weekday_at_exact_close(self, mock_dt):
        mock_dt.now.return_value = self._kst(0, 15, 30)  # 월요일 15:30
        assert _is_market_hours() is True

    @patch("app.services.trading_engine.datetime")
    def test_saturday_returns_false(self, mock_dt):
        mock_dt.now.return_value = self._kst(5, 10, 0)   # 토요일 10:00
        assert _is_market_hours() is False

    @patch("app.services.trading_engine.datetime")
    def test_sunday_returns_false(self, mock_dt):
        mock_dt.now.return_value = self._kst(6, 10, 0)   # 일요일 10:00
        assert _is_market_hours() is False


# ─── MockBroker ────────────────────────────────────────────────────────────────

class TestMockBroker:
    """MockBroker는 Supabase 의존성 때문에 DB 호출을 모킹"""

    @pytest.mark.asyncio
    async def test_buy_success(self):
        from app.brokers.mock_broker import MockBroker
        broker = MockBroker()

        with patch.object(broker, "_get_balance_sync", return_value=5_000_000), \
             patch.object(broker, "_update_balance_sync") as mock_update, \
             patch.object(broker, "_insert_position_sync") as mock_pos, \
             patch.object(broker, "_insert_trade_history_sync") as mock_hist:

            result = await broker.buy("005930", "삼성전자", 70_000, 10,
                                      stop_loss_price=66_500, take_profit_price=77_000)

        assert result["success"] is True
        assert "매수 완료" in result["message"]
        mock_update.assert_called_once_with(5_000_000 - 70_000 * 10)
        mock_pos.assert_called_once()
        mock_hist.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_insufficient_balance(self):
        from app.brokers.mock_broker import MockBroker
        broker = MockBroker()

        with patch.object(broker, "_get_balance_sync", return_value=100_000):
            result = await broker.buy("005930", "삼성전자", 70_000, 10)

        assert result["success"] is False
        assert "잔고 부족" in result["message"]

    @pytest.mark.asyncio
    async def test_sell_no_position(self):
        from app.brokers.mock_broker import MockBroker
        broker = MockBroker()

        with patch.object(broker, "_get_position_sync", return_value=None):
            result = await broker.sell("005930", "삼성전자", 72_000, 10)

        assert result["success"] is False
        assert "보유 포지션 없음" in result["message"]

    @pytest.mark.asyncio
    async def test_sell_profit(self):
        from app.brokers.mock_broker import MockBroker
        broker = MockBroker()

        position = {
            "id": "test-uuid",
            "entry_price": 70_000,
            "quantity": 10,
        }
        with patch.object(broker, "_get_position_sync", return_value=position), \
             patch.object(broker, "_get_balance_sync", return_value=3_000_000), \
             patch.object(broker, "_update_balance_sync") as mock_update, \
             patch.object(broker, "_delete_position_sync") as mock_del, \
             patch.object(broker, "_insert_trade_history_sync") as mock_hist:

            result = await broker.sell("005930", "삼성전자", 75_000, 10)

        assert result["success"] is True
        assert "매도 완료" in result["message"]
        # 수익: (75000 - 70000) * 10 = 50,000원
        expected_balance = 3_000_000 + 75_000 * 10
        mock_update.assert_called_once_with(expected_balance)
        # profit_loss = (75000 - 70000) * 10 = 50000
        call_args = mock_hist.call_args[0]
        assert call_args[6] == 50_000   # profit_loss positional arg
