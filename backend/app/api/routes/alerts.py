from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.models.theme import Alert, AlertCreate
from app.services import alert_monitor

router = APIRouter()


@router.get("/alerts/history")
async def get_alert_history(limit: int = 50):
    from app.services.alert_monitor import _db_get_history
    import asyncio
    return await asyncio.to_thread(_db_get_history, limit)


@router.get("/alerts", response_model=list[Alert])
async def list_alerts():
    return await alert_monitor.get_alerts()


@router.post("/alerts", response_model=Alert)
async def add_alert(data: AlertCreate):
    return await alert_monitor.create_alert(data)


@router.delete("/alerts/{alert_id}", status_code=204)
async def remove_alert(alert_id: str):
    deleted = await alert_monitor.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")


@router.patch("/alerts/{alert_id}", response_model=Alert)
async def toggle_alert_endpoint(alert_id: str):
    result = await alert_monitor.toggle_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await websocket.accept()
    alert_monitor.register_websocket(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_monitor.unregister_websocket(websocket)
