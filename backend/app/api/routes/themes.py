from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException

from app.db import get_supabase
from app.models.theme import ThemeStrength, ThemeDetail, Theme
from app.services.theme_service import (
    load_themes,
    get_all_theme_strengths,
    get_theme_detail,
)

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("/", response_model=List[ThemeStrength])
async def list_themes():
    return await get_all_theme_strengths()


@router.get("/{theme_id}/history")
async def get_theme_history(theme_id: str, period: str = "1d"):
    """당일 또는 지정 기간 테마 강도 추이 조회"""
    hours = 24 if period == "1d" else 1
    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    def _fetch():
        sb = get_supabase()
        return sb.table("theme_history") \
            .select("avg_change_rate,rising_count,falling_count,total,recorded_at") \
            .eq("theme_id", theme_id) \
            .gte("recorded_at", since) \
            .order("recorded_at") \
            .execute()

    res = await asyncio.to_thread(_fetch)
    return res.data or []


@router.get("/{theme_id}", response_model=ThemeDetail)
async def get_theme(theme_id: str):
    detail = await get_theme_detail(theme_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_id}' not found")
    return detail
