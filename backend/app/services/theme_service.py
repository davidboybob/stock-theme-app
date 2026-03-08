from __future__ import annotations

import json
import asyncio
from pathlib import Path
from statistics import mean
from typing import List
from app.models.theme import Theme, ThemeStrength, ThemeDetail
from app.models.stock import StockPrice
from app.services.kis_client import kis_client

_themes_cache: List[Theme] = []


def load_themes() -> List[Theme]:
    global _themes_cache
    if _themes_cache:
        return _themes_cache
    data_path = Path(__file__).parent.parent / "data" / "themes.json"
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    _themes_cache = [Theme(**t) for t in data["themes"]]
    return _themes_cache


def get_theme_by_id(theme_id: str) -> Theme | None:
    return next((t for t in load_themes() if t.id == theme_id), None)


async def get_theme_strength(theme: Theme) -> ThemeStrength:
    try:
        prices = await asyncio.gather(
            *[kis_client.get_stock_price(code) for code in theme.stocks],
            return_exceptions=True,
        )
        valid_prices = [p for p in prices if isinstance(p, StockPrice)]
        if not valid_prices:
            avg_change = 0.0
            rising = 0
            falling = 0
        else:
            avg_change = mean(p.change_rate for p in valid_prices)
            rising = sum(1 for p in valid_prices if p.change_rate > 0)
            falling = sum(1 for p in valid_prices if p.change_rate < 0)
    except Exception:
        avg_change = 0.0
        rising = 0
        falling = 0

    return ThemeStrength(
        theme_id=theme.id,
        theme_name=theme.name,
        avg_change_rate=round(avg_change, 2),
        rising_count=rising,
        falling_count=falling,
        total=len(theme.stocks),
    )


async def get_theme_detail(theme_id: str) -> ThemeDetail | None:
    theme = get_theme_by_id(theme_id)
    if not theme:
        return None

    prices_raw = await asyncio.gather(
        *[kis_client.get_stock_price(code) for code in theme.stocks],
        return_exceptions=True,
    )
    stock_prices = [p for p in prices_raw if isinstance(p, StockPrice)]

    strength = await get_theme_strength(theme)
    return ThemeDetail(
        id=theme.id,
        name=theme.name,
        description=theme.description,
        strength=strength,
        stock_prices=stock_prices,
    )


async def get_all_theme_strengths() -> List[ThemeStrength]:
    themes = load_themes()
    strengths = await asyncio.gather(*[get_theme_strength(t) for t in themes])
    return sorted(strengths, key=lambda s: s.avg_change_rate, reverse=True)
