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

-- RLS 비활성화 (서버사이드 전용)
ALTER TABLE alerts DISABLE ROW LEVEL SECURITY;
ALTER TABLE alert_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE theme_history DISABLE ROW LEVEL SECURITY;
