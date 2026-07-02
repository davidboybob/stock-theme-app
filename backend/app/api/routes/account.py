"""계좌·자산 조회 라우트.

TRADING_ENABLED=true 일 때만 main.py 에서 라우터가 등록된다.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.toss_auth import TossAuthError
from app.models.portfolio import Account, PortfolioSummary, parse_account, parse_holdings
from app.services.toss_client import TossApiError, get_toss_client

router = APIRouter(prefix="/account", tags=["account"])


def _handle(e: Exception) -> HTTPException:
    if isinstance(e, TossApiError):
        return HTTPException(
            status_code=e.status_code,
            detail={"code": e.code, "message": e.message, "request_id": e.request_id},
        )
    if isinstance(e, TossAuthError):
        return HTTPException(status_code=500, detail={"code": "auth-config", "message": str(e)})
    return HTTPException(status_code=500, detail={"code": "internal", "message": str(e)})


@router.get("", response_model=list[Account])
async def get_accounts():
    """토스증권 계좌 목록."""
    try:
        raw = await get_toss_client().get_accounts()
        return [parse_account(a) for a in raw]
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)


@router.get("/holdings", response_model=PortfolioSummary)
async def get_holdings(
    account_seq: int = Query(..., description="GET /api/account 응답의 account_seq"),
    symbol: Optional[str] = Query(None, description="특정 종목만 필터 (예: 005930)"),
):
    """보유 주식 + 평가손익 요약."""
    try:
        raw = await get_toss_client().get_holdings(account_seq, symbol)
        return parse_holdings(raw)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)
