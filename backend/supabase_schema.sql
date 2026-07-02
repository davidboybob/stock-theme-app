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

-- orders_log 테이블 (토스증권 주문 이력 — 모든 주문 시도 기록)
CREATE TABLE IF NOT EXISTS orders_log (
    id BIGSERIAL PRIMARY KEY,
    account_seq BIGINT NOT NULL,
    action TEXT NOT NULL,              -- CREATE / MODIFY / CANCEL
    source TEXT NOT NULL DEFAULT 'manual',  -- manual / bot
    symbol TEXT,
    side TEXT,                         -- BUY / SELL
    order_type TEXT,                   -- LIMIT / MARKET
    quantity REAL,
    price REAL,
    order_id TEXT,
    client_order_id TEXT,
    status TEXT,
    success BOOLEAN,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_log_account ON orders_log (account_seq, created_at DESC);

-- trade_signals 테이블 (자동매매 시그널 — dry-run 품질 검증용)
CREATE TABLE IF NOT EXISTS trade_signals (
    id BIGSERIAL PRIMARY KEY,
    strategy TEXT NOT NULL,
    action TEXT NOT NULL,              -- BUY / SELL
    symbol TEXT NOT NULL,
    symbol_name TEXT,
    theme_id TEXT,
    theme_name TEXT,
    price REAL,
    quantity REAL,
    reason TEXT,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    executed BOOLEAN NOT NULL DEFAULT FALSE,
    order_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trade_signals_created ON trade_signals (created_at DESC);

-- bot_runs 테이블 (봇 시작/중지 이력)
CREATE TABLE IF NOT EXISTS bot_runs (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL,               -- START / STOP
    dry_run BOOLEAN,
    interval_minutes INTEGER,
    threshold REAL,
    created_at TEXT NOT NULL
);

-- RLS 비활성화 (서버사이드 전용)
ALTER TABLE alerts DISABLE ROW LEVEL SECURITY;
ALTER TABLE alert_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE theme_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE orders_log DISABLE ROW LEVEL SECURITY;
ALTER TABLE trade_signals DISABLE ROW LEVEL SECURITY;
ALTER TABLE bot_runs DISABLE ROW LEVEL SECURITY;
