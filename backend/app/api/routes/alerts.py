from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
from app.models.theme import Alert, AlertCreate
from app.services import alert_monitor
from app.db import DB_PATH
import aiosqlite

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=List[Alert])
async def list_alerts():
    return await alert_monitor.get_alerts()


@router.post("/alerts", response_model=Alert)
async def create_alert(data: AlertCreate):
    return await alert_monitor.create_alert(data)


@router.get("/alerts/history")
async def get_alert_history(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM alert_history ORDER BY triggered_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.patch("/alerts/{alert_id}", response_model=Alert)
async def toggle_alert_endpoint(alert_id: str):
    result = await alert_monitor.toggle_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    deleted = await alert_monitor.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted"}


@router.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket):
    await ws.accept()
    alert_monitor.register_websocket(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        alert_monitor.unregister_websocket(ws)
