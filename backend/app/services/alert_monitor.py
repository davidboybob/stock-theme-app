from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Set
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiosqlite

from app.db import get_db, DB_PATH
from app.models.theme import Alert, AlertCreate, AlertTriggered
from app.services.naver_client import naver_client as kis_client
from app.services.theme_service import get_theme_strength, get_theme_by_id, get_all_theme_strengths

_websocket_clients: Set = set()
_scheduler: AsyncIOScheduler | None = None


async def get_alerts() -> List[Alert]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM alerts ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
    result = []
    for row in rows:
        row_dict = dict(row)
        row_dict["is_active"] = bool(row_dict["is_active"])
        result.append(Alert(**row_dict))
    return result


async def create_alert(data: AlertCreate) -> Alert:
    theme = get_theme_by_id(data.target_id)
    target_name = theme.name if theme else data.target_id
    alert = Alert(
        id=str(uuid.uuid4()),
        target_type=data.target_type,
        target_id=data.target_id,
        target_name=target_name,
        condition=data.condition,
        threshold=data.threshold,
        is_active=True,
        created_at=datetime.now().isoformat(),
    )
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?)",
            (alert.id, alert.target_type, alert.target_id, alert.target_name,
             alert.condition, alert.threshold, int(alert.is_active), alert.created_at)
        )
        await db.commit()
    return alert


async def toggle_alert(alert_id: str) -> Optional[Alert]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        new_active = 0 if row["is_active"] else 1
        await db.execute("UPDATE alerts SET is_active=? WHERE id=?", (new_active, alert_id))
        await db.commit()
        async with db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)) as cursor:
            updated = await cursor.fetchone()
    row_dict = dict(updated)
    row_dict["is_active"] = bool(row_dict["is_active"])
    return Alert(**row_dict)


async def delete_alert(alert_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
        await db.commit()
    return cursor.rowcount > 0


def register_websocket(ws) -> None:
    _websocket_clients.add(ws)


def unregister_websocket(ws) -> None:
    _websocket_clients.discard(ws)


async def _broadcast(message: dict) -> None:
    dead = set()
    for ws in _websocket_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _websocket_clients.discard(ws)


async def _check_alerts() -> None:
    alerts = [a for a in await get_alerts() if a.is_active]
    for alert in alerts:
        try:
            if alert.target_type == "theme":
                theme = get_theme_by_id(alert.target_id)
                if not theme:
                    continue
                strength = await get_theme_strength(theme)
                current_value = strength.avg_change_rate
            else:
                price = await kis_client.get_stock_price(alert.target_id)
                current_value = price.change_rate

            triggered = (
                alert.condition == "above" and current_value >= alert.threshold
            ) or (alert.condition == "below" and current_value <= alert.threshold)

            if triggered:
                notification = AlertTriggered(
                    alert_id=alert.id,
                    target_name=alert.target_name,
                    current_value=current_value,
                    threshold=alert.threshold,
                    condition=alert.condition,
                    triggered_at=datetime.now().isoformat(),
                )
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT INTO alert_history (alert_id, target_name, current_value, threshold, condition, triggered_at) VALUES (?,?,?,?,?,?)",
                        (alert.id, alert.target_name, current_value, alert.threshold, alert.condition, notification.triggered_at)
                    )
                    await db.commit()
                await _broadcast(notification.model_dump())
        except Exception:
            pass


async def _snapshot_themes() -> None:
    """10분마다 전체 테마 강도 스냅샷 저장"""
    try:
        strengths = await get_all_theme_strengths()
        now = datetime.now().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            for s in strengths:
                await db.execute(
                    "INSERT INTO theme_history (theme_id, theme_name, avg_change_rate, rising_count, falling_count, total, recorded_at) VALUES (?,?,?,?,?,?,?)",
                    (s.theme_id, s.theme_name, s.avg_change_rate, s.rising_count, s.falling_count, s.total, now)
                )
            await db.commit()
    except Exception:
        pass


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_check_alerts, "interval", minutes=1, id="alert_monitor")
    _scheduler.add_job(_snapshot_themes, "interval", minutes=10, id="theme_snapshot")
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
