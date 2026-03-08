from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
from app.models.theme import Alert, AlertCreate
from app.services import alert_monitor

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=List[Alert])
async def list_alerts():
    return alert_monitor.get_alerts()


@router.post("/alerts", response_model=Alert)
async def create_alert(data: AlertCreate):
    return alert_monitor.create_alert(data)


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    deleted = alert_monitor.delete_alert(alert_id)
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
