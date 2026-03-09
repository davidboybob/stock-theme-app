from __future__ import annotations

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "alerts.db"


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_name TEXT NOT NULL,
                condition TEXT NOT NULL,
                threshold REAL NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                target_name TEXT NOT NULL,
                current_value REAL NOT NULL,
                threshold REAL NOT NULL,
                condition TEXT NOT NULL,
                triggered_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS theme_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id TEXT NOT NULL,
                theme_name TEXT NOT NULL,
                avg_change_rate REAL NOT NULL,
                rising_count INTEGER NOT NULL,
                falling_count INTEGER NOT NULL,
                total INTEGER NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)
        await db.commit()
