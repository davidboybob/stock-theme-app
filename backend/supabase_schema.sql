-- alerts 테이블
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_name TEXT NOT NULL,
    condition TEXT NOT NULL,
    threshold REAL NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TEXT NOT NULL
);

-- alert_history 테이블
CREATE TABLE IF NOT EXISTS alert_history (
    id BIGSERIAL PRIMARY KEY,
    alert_id TEXT NOT NULL,
    target_name TEXT NOT NULL,
    current_value REAL NOT NULL,
    threshold REAL NOT NULL,
    condition TEXT NOT NULL,
    triggered_at TEXT NOT NULL
);

-- theme_history 테이블
CREATE TABLE IF NOT EXISTS theme_history (
    id BIGSERIAL PRIMARY KEY,
    theme_id TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    avg_change_rate REAL NOT NULL,
    rising_count INTEGER NOT NULL,
    falling_count INTEGER NOT NULL,
    total INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);

-- ──────────────────────────────────────────────
-- 자동매매 테이블
-- ──────────────────────────────────────────────

-- 감시 종목 목록
CREATE TABLE IF NOT EXISTS watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    theme_id TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 전략 설정 (단일 행 운용)
CREATE TABLE IF NOT EXISTS trading_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    short_ma INTEGER NOT NULL DEFAULT 5,
    long_ma INTEGER NOT NULL DEFAULT 20,
    stop_loss_pct REAL NOT NULL DEFAULT 5.0,
    take_profit_pct REAL NOT NULL DEFAULT 10.0,
    paper_initial_capital BIGINT NOT NULL DEFAULT 10000000,
    paper_balance BIGINT NOT NULL DEFAULT 10000000,
    is_running BOOLEAN NOT NULL DEFAULT FALSE,
    strategy TEXT NOT NULL DEFAULT 'ma_cross',
    rsi_period INTEGER NOT NULL DEFAULT 14,
    rsi_oversold REAL NOT NULL DEFAULT 30.0,
    rsi_overbought REAL NOT NULL DEFAULT 70.0,
    macd_fast INTEGER NOT NULL DEFAULT 12,
    macd_slow INTEGER NOT NULL DEFAULT 26,
    macd_signal INTEGER NOT NULL DEFAULT 9,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 현재 보유 포지션
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'real')),
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price BIGINT NOT NULL,
    stop_loss_price BIGINT NOT NULL,
    take_profit_price BIGINT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 거래 내역
CREATE TABLE IF NOT EXISTS trade_history (
    id BIGSERIAL PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'real')),
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN ('BUY', 'SELL')),
    price BIGINT NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    profit_loss BIGINT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 일봉 종가 스냅샷 (16:10 KST 저장)
CREATE TABLE IF NOT EXISTS daily_price_snapshot (
    id BIGSERIAL PRIMARY KEY,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    close_price BIGINT NOT NULL,
    recorded_at DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (stock_code, recorded_at)
);

-- ──────────────────────────────────────────────
-- RLS 비활성화 (서버사이드 전용)
-- ──────────────────────────────────────────────
ALTER TABLE alerts DISABLE ROW LEVEL SECURITY;
ALTER TABLE alert_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE theme_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist DISABLE ROW LEVEL SECURITY;
ALTER TABLE trading_config DISABLE ROW LEVEL SECURITY;
ALTER TABLE positions DISABLE ROW LEVEL SECURITY;
ALTER TABLE trade_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_price_snapshot DISABLE ROW LEVEL SECURITY;
