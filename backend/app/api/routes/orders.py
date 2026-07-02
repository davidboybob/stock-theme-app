"""주문 라우트. TRADING_ENABLED=true 일 때만 등록된다."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.toss_auth import TossAuthError
from app.models.trading import OrderCreateIn, OrderModifyIn, OrderOut
from app.services import order_service
from app.services.toss_client import TossApiError, get_toss_client

router = APIRouter(prefix="/orders", tags=["orders"])


def _handle(e: Exception) -> HTTPException:
    if isinstance(e, TossApiError):
        return HTTPException(
            status_code=e.status_code,
            detail={
                "code": e.code,
                "message": e.message,
                "data": e.data,
                "request_id": e.request_id,
            },
        )
    if isinstance(e, TossAuthError):
        return HTTPException(status_code=500, detail={"code": "auth-config", "message": str(e)})
    return HTTPException(status_code=500, detail={"code": "internal", "message": str(e)})


@router.post("", response_model=OrderOut)
async def create_order(body: OrderCreateIn, account_seq: int = Query(...)):
    """주문 생성 (KRX 지정가/시장가)."""
    try:
        return await order_service.create_order(account_seq, body)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid-request", "message": str(e)})


@router.get("", response_model=list[OrderOut])
async def list_open_orders(
    account_seq: int = Query(...),
    symbol: Optional[str] = Query(None),
):
    """대기중(OPEN) 주문 목록."""
    try:
        return await order_service.get_open_orders(account_seq, symbol)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)


@router.get("/log")
async def order_log(account_seq: int = Query(...), limit: int = Query(50, le=200)):
    """로컬 주문 이력 (Supabase orders_log)."""
    return order_service.get_order_log(account_seq, limit)


@router.get("/buying-power")
async def buying_power(account_seq: int = Query(...)):
    """매수 가능 금액 (KRW)."""
    try:
        return await get_toss_client().get_buying_power(account_seq, "KRW")
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)


@router.get("/sellable-quantity")
async def sellable_quantity(account_seq: int = Query(...), symbol: str = Query(...)):
    """판매 가능 수량."""
    try:
        return await get_toss_client().get_sellable_quantity(account_seq, symbol)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, account_seq: int = Query(...)):
    """주문 상세 (모든 상태)."""
    try:
        return await order_service.get_order(account_seq, order_id)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)


@router.post("/{order_id}/modify", response_model=OrderOut)
async def modify_order(order_id: str, body: OrderModifyIn, account_seq: int = Query(...)):
    """주문 정정 (가격/수량)."""
    try:
        return await order_service.modify_order(account_seq, order_id, body)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(order_id: str, account_seq: int = Query(...)):
    """주문 취소."""
    try:
        return await order_service.cancel_order(account_seq, order_id)
    except (TossApiError, TossAuthError) as e:
        raise _handle(e)
