from fastapi import APIRouter, HTTPException
from typing import List
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


@router.get("/{theme_id}", response_model=ThemeDetail)
async def get_theme(theme_id: str):
    detail = await get_theme_detail(theme_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_id}' not found")
    return detail
