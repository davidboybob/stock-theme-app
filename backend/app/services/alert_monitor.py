from __future__ import annotations

import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Set
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.models.theme import Alert, AlertCreate, AlertTriggered
from app.services.naver_client import naver_client as kis_client
from app.services.theme_service import get_theme_strength, get_theme_by_id

_alerts_file = Path(__file__).parent.parent / "data" / "alerts.json"
_websocket_clients: Set = set()
_scheduler: AsyncIOScheduler | None = None


def _load_alerts() -> List[Alert]:
    if not _alerts_file.exists():
        return []
    with open(_alerts_file, encoding="utf-8") as f:
        data = json.load(f)
    return [Alert(**a) for a in data]


def _save_alerts(alerts: List[Alert]) -> None:
    _alerts_file.parent.mkdir(parents=True, exist_ok=True)
    with open(_alerts_file, "w", encoding="utf-8") as f:
        json.dump([a.model_dump() for a in alerts], f, ensure_ascii=False, indent=2)


def get_alerts() -> List[Alert]:
    return _load_alerts()


def create_alert(data: AlertCreate) -> Alert:
    alerts = _load_alerts()
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
    alerts.append(alert)
    _save_alerts(alerts)
    return alert


def delete_alert(alert_id: str) -> bool:
    alerts = _load_alerts()
    new_alerts = [a for a in alerts if a.id != alert_id]
    if len(new_alerts) == len(alerts):
        return False
    _save_alerts(new_alerts)
    return True


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
    alerts = [a for a in _load_alerts() if a.is_active]
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
                await _broadcast(notification.model_dump())
        except Exception:
            pass


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_check_alerts, "interval", minutes=1, id="alert_monitor")
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
