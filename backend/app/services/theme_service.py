from __future__ import annotations

import json
import asyncio
import time
from pathlib import Path
from statistics import mean
from typing import Dict, List
from app.models.theme import Theme, ThemeStrength, ThemeDetail
from app.models.stock import StockPrice
from app.services.naver_client import naver_client as kis_client

_themes_cache: List[Theme] = []

# 무료 인스턴스(512MB)에서 요청마다 80종목 동시 수집 시 과부하로 재시작되므로
# 강도 목록은 60초 캐시 + 단일 수집 잠금으로 보호한다.
# 만료 후에도 낡은 값을 즉시 반환하고 백그라운드에서 갱신(stale-while-revalidate)해
# 화면 전환이 수집 시간(수 초)을 기다리지 않게 한다.
_STRENGTHS_TTL = 60.0
_strengths_cache: dict = {"data": None, "ts": 0.0}
_strengths_lock = asyncio.Lock()

# 테마 상세도 동일 전략 — 상세 1회 = 종목 10개 실시간 수집이라 캐시 없이는 매번 수 초 걸린다
_DETAIL_TTL = 60.0
_detail_cache: Dict[str, dict] = {}
_detail_locks: Dict[str, asyncio.Lock] = {}


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


def _strength_from_prices(theme: Theme, valid_prices: List[StockPrice]) -> ThemeStrength:
    if not valid_prices:
        avg_change = 0.0
        rising = 0
        falling = 0
    else:
        avg_change = mean(p.change_rate for p in valid_prices)
        rising = sum(1 for p in valid_prices if p.change_rate > 0)
        falling = sum(1 for p in valid_prices if p.change_rate < 0)
    return ThemeStrength(
        theme_id=theme.id,
        theme_name=theme.name,
        avg_change_rate=round(avg_change, 2),
        rising_count=rising,
        falling_count=falling,
        total=len(theme.stocks),
    )


async def _fetch_theme_prices(theme: Theme) -> List[StockPrice]:
    prices = await asyncio.gather(
        *[kis_client.get_stock_price(s.code) for s in theme.stocks],
        return_exceptions=True,
    )
    return [p for p in prices if isinstance(p, StockPrice)]


async def get_theme_strength(theme: Theme) -> ThemeStrength:
    try:
        valid_prices = await _fetch_theme_prices(theme)
    except Exception:
        valid_prices = []
    return _strength_from_prices(theme, valid_prices)


async def _refresh_detail(theme: Theme) -> None:
    lock = _detail_locks.setdefault(theme.id, asyncio.Lock())
    async with lock:
        entry = _detail_cache.get(theme.id)
        if entry is not None and time.monotonic() - entry["ts"] < _DETAIL_TTL:
            return
        try:
            stock_prices = await _fetch_theme_prices(theme)
        except Exception:
            stock_prices = []
        if not stock_prices and entry is not None:
            # 수집 전부 실패 — 기존 데이터 유지, ts만 갱신해 재시도 폭주 방지
            entry["ts"] = time.monotonic()
            return
        detail = ThemeDetail(
            id=theme.id,
            name=theme.name,
            description=theme.description,
            # 강도는 방금 수집한 시세로 계산 — 종목 재수집(2중 호출) 금지
            strength=_strength_from_prices(theme, stock_prices),
            stock_prices=stock_prices,
        )
        _detail_cache[theme.id] = {"data": detail, "ts": time.monotonic()}


async def get_theme_detail(theme_id: str) -> ThemeDetail | None:
    theme = get_theme_by_id(theme_id)
    if not theme:
        return None

    entry = _detail_cache.get(theme_id)
    if entry is not None:
        if time.monotonic() - entry["ts"] < _DETAIL_TTL:
            return entry["data"]
        # 만료 — 낡은 값 즉시 반환하고 백그라운드에서 갱신
        lock = _detail_locks.setdefault(theme_id, asyncio.Lock())
        if not lock.locked():
            asyncio.create_task(_refresh_detail(theme))
        return entry["data"]

    await _refresh_detail(theme)
    entry = _detail_cache.get(theme_id)
    return entry["data"] if entry else None


async def _refresh_strengths() -> None:
    async with _strengths_lock:
        now = time.monotonic()
        if _strengths_cache["data"] is not None and now - _strengths_cache["ts"] < _STRENGTHS_TTL:
            return
        themes = load_themes()
        # 테마 단위 순차 수집 — 동시 요청을 테마당 종목 수(10)로 제한
        strengths = [await get_theme_strength(t) for t in themes]
        result = sorted(strengths, key=lambda s: s.avg_change_rate, reverse=True)
        _strengths_cache["data"] = result
        _strengths_cache["ts"] = time.monotonic()


async def get_all_theme_strengths() -> List[ThemeStrength]:
    if _strengths_cache["data"] is not None:
        if time.monotonic() - _strengths_cache["ts"] < _STRENGTHS_TTL:
            return _strengths_cache["data"]
        # 만료 — 낡은 값 즉시 반환하고 백그라운드에서 갱신
        if not _strengths_lock.locked():
            asyncio.create_task(_refresh_strengths())
        return _strengths_cache["data"]

    await _refresh_strengths()
    return _strengths_cache["data"] or []
