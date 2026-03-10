from __future__ import annotations

import uuid
import asyncio
from datetime import datetime
from typing import List, Set, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db import get_supabase
from app.models.theme import Alert, AlertCreate, AlertTriggered
from app.services.naver_client import naver_client as kis_client
from app.services.theme_service import get_theme_strength, get_theme_by_id

_websocket_clients: Set = set()
_scheduler: AsyncIOScheduler | None = None


def _db_get_alerts() -> List[Alert]:
    sb = get_supabase()
    res = sb.table("alerts").select("*").order("created_at", desc=True).execute()
    return [Alert(**{**row, "is_active": bool(row["is_active"])}) for row in (res.data or [])]


def _db_create_alert(alert: Alert) -> None:
    sb = get_supabase()
    sb.table("alerts").insert({
        "id": alert.id,
        "target_type": alert.target_type,
        "target_id": alert.target_id,
        "target_name": alert.target_name,
        "condition": alert.condition,
        "threshold": alert.threshold,
        "is_active": alert.is_active,
        "created_at": alert.created_at,
    }).execute()


def _db_delete_alert(alert_id: str) -> bool:
    sb = get_supabase()
    res = sb.table("alerts").delete().eq("id", alert_id).execute()
    return len(res.data or []) > 0


def _db_toggle_alert(alert_id: str) -> Optional[Alert]:
    sb = get_supabase()
    row = sb.table("alerts").select("*").eq("id", alert_id).single().execute()
    if not row.data:
        return None
    new_active = not row.data["is_active"]
    updated = sb.table("alerts").update({"is_active": new_active}).eq("id", alert_id).execute()
    if not updated.data:
        return None
    d = updated.data[0]
    return Alert(**{**d, "is_active": bool(d["is_active"])})


def _db_insert_history(alert_id: str, target_name: str, current_value: float,
                        threshold: float, condition: str, triggered_at: str) -> None:
    sb = get_supabase()
    sb.table("alert_history").insert({
        "alert_id": alert_id,
        "target_name": target_name,
        "current_value": current_value,
        "threshold": threshold,
        "condition": condition,
        "triggered_at": triggered_at,
    }).execute()


def _db_get_history(limit: int = 50) -> list:
    sb = get_supabase()
    res = sb.table("alert_history").select("*").order("triggered_at", desc=True).limit(limit).execute()
    return res.data or []


async def get_alerts() -> List[Alert]:
    return await asyncio.to_thread(_db_get_alerts)


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
    await asyncio.to_thread(_db_create_alert, alert)
    return alert


async def delete_alert(alert_id: str) -> bool:
    return await asyncio.to_thread(_db_delete_alert, alert_id)


async def toggle_alert(alert_id: str) -> Optional[Alert]:
    return await asyncio.to_thread(_db_toggle_alert, alert_id)


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
                await asyncio.to_thread(
                    _db_insert_history,
                    alert.id, alert.target_name, current_value,
                    alert.threshold, alert.condition, notification.triggered_at,
                )
                await _broadcast(notification.model_dump())
        except Exception:
            pass


async def _snapshot_themes() -> None:
    try:
        from app.services.theme_service import get_all_theme_strengths
        strengths = await get_all_theme_strengths()
        now = datetime.now().isoformat()
        sb = get_supabase()
        rows = [
            {
                "theme_id": s.theme_id,
                "theme_name": s.theme_name,
                "avg_change_rate": s.avg_change_rate,
                "rising_count": s.rising_count,
                "falling_count": s.falling_count,
                "total": s.total,
                "recorded_at": now,
            }
            for s in strengths
        ]
        await asyncio.to_thread(lambda: sb.table("theme_history").insert(rows).execute())
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
