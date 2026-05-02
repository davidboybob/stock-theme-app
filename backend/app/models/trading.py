from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List


class WatchlistItem(BaseModel):
    id: str
    stock_code: str
    stock_name: str
    theme_id: Optional[str] = None
    is_active: bool = True
    added_at: str


class WatchlistAdd(BaseModel):
    stock_code: str
    stock_name: str
    theme_id: Optional[str] = None


class TradingConfig(BaseModel):
    id: Optional[str] = None
    short_ma: int = 5
    long_ma: int = 20
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    paper_initial_capital: int = 10_000_000
    paper_balance: int = 10_000_000
    is_running: bool = False
    strategy: str = "ma_cross"  # ma_cross | rsi | macd
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


class TradingConfigUpdate(BaseModel):
    short_ma: Optional[int] = None
    long_ma: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    strategy: Optional[str] = None
    rsi_period: Optional[int] = None
    rsi_oversold: Optional[float] = None
    rsi_overbought: Optional[float] = None
    macd_fast: Optional[int] = None
    macd_slow: Optional[int] = None
    macd_signal: Optional[int] = None


class Position(BaseModel):
    id: str
    mode: str
    stock_code: str
    stock_name: str
    quantity: int
    entry_price: int
    stop_loss_price: int
    take_profit_price: int
    entered_at: str
    # New fields (optional, enriched at query time)
    current_price: Optional[int] = None
    unrealized_profit_loss: Optional[int] = None
    return_rate: Optional[float] = None


class TradeHistory(BaseModel):
    id: int
    mode: str
    stock_code: str
    stock_name: str
    signal_type: str
    price: int
    quantity: int
    reason: str
    profit_loss: Optional[int] = None
    executed_at: str


class TradingSignal(BaseModel):
    """WebSocket으로 브로드캐스트되는 매매 시그널"""
    stock_code: str
    stock_name: str
    signal_type: str   # BUY, SELL
    price: int
    quantity: int
    reason: str        # golden_cross, dead_cross, stop_loss, take_profit
    mode: str          # paper, real
    message: str
    timestamp: str


class BacktestRequest(BaseModel):
    stock_codes: List[str]
    stock_names: Optional[List[str]] = None  # 코드와 1:1 매핑 (없으면 코드로 대체)
    strategy: str = "ma_cross"
    short_ma: int = 5
    long_ma: int = 20
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    initial_capital: int = 10_000_000
    count: int = 180  # 조회 일수 (최대 180일)
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal_period: int = 9


class BacktestTrade(BaseModel):
    index: int          # 시뮬레이션 인덱스
    signal_type: str    # BUY | SELL
    price: int
    quantity: int
    reason: str
    profit_loss: Optional[int] = None
    balance_after: int


class BacktestStockResult(BaseModel):
    stock_code: str
    stock_name: str
    strategy: str
    initial_capital: int
    final_balance: int
    return_rate: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    max_drawdown: float
    trades: List[BacktestTrade]


class BacktestResult(BaseModel):
    strategy: str
    initial_capital: int
    results: List[BacktestStockResult]
    # 합산 지표
    total_return_rate: float
    avg_win_rate: float
    avg_max_drawdown: float
