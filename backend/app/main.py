from __future__ import annotations

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import themes, stocks, alerts, trading
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) or "Internal server error"},
    )


app.include_router(themes.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(trading.router, prefix="/api")


@app.get("/api/health")
async def health():
    supabase_ok = (
        os.getenv("SUPABASE_URL", "").startswith("https://")
        and "placeholder" not in os.getenv("SUPABASE_URL", "")
    )
    return {
        "status": "ok",
        "supabase": "connected" if supabase_ok else "not configured",
        "version": "1.0.0",
    }
