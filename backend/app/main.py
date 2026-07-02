from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import themes, stocks, alerts
from app.core.config import get_settings
from app.services.alert_monitor import start_scheduler, stop_scheduler
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="테마주 분석 API",
    description="한국 주식 테마별 종목 분석 서비스",
    version="1.0.0",
    lifespan=lifespan,
)

import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(themes.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")

# 트레이딩(토스증권) 기능 — TRADING_ENABLED=true 인 환경에서만 노출
if get_settings().trading_enabled:
    from app.api.routes import account, orders

    app.include_router(account.router, prefix="/api")
    app.include_router(orders.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "trading": get_settings().trading_enabled}
