"""주문 실행 + Supabase 로그.

모든 주문 시도(성공/실패)를 orders_log 테이블에 기록한다.
토스 API가 종료된 주문 목록 조회를 아직 지원하지 않으므로,
이 로그가 로컬 주문 이력의 source of truth 역할을 한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from app.db import get_supabase
from app.models.trading import OrderCreateIn, OrderModifyIn, OrderOut, parse_order
from app.services.toss_client import TossApiError, get_toss_client


def _log(entry: dict) -> None:
    """주문 로그 기록. 로그 실패가 주문 흐름을 막으면 안 되므로 예외는 삼킨다."""
    try:
        get_supabase().table("orders_log").insert(entry).execute()
    except Exception as e:
        import warnings
        warnings.warn(f"orders_log 기록 실패: {e}")


def _base_entry(account_seq: int, action: str, source: str = "manual") -> dict:
    return {
        "account_seq": account_seq,
        "action": action,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def create_order(
    account_seq: int, order: OrderCreateIn, source: str = "manual"
) -> OrderOut:
    # 멱등성 키 자동 생성 (재시도로 인한 중복 주문 방지)
    if not order.client_order_id:
        order.client_order_id = uuid.uuid4().hex[:32]

    entry = _base_entry(account_seq, "CREATE", source)
    entry.update(
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        client_order_id=order.client_order_id,
    )

    try:
        raw = await get_toss_client().create_order(account_seq, order.to_toss_payload())
        parsed = parse_order(raw)
        entry.update(order_id=parsed.order_id, status=parsed.status, success=True)
        _log(entry)
        return parsed
    except TossApiError as e:
        entry.update(success=False, error_code=e.code, error_message=e.message)
        _log(entry)
        raise


async def modify_order(account_seq: int, order_id: str, body: OrderModifyIn) -> OrderOut:
    entry = _base_entry(account_seq, "MODIFY")
    entry.update(order_id=order_id, quantity=body.quantity, price=body.price)
    try:
        raw = await get_toss_client().modify_order(account_seq, order_id, body.to_toss_payload())
        parsed = parse_order(raw)
        entry.update(status=parsed.status, success=True)
        _log(entry)
        return parsed
    except TossApiError as e:
        entry.update(success=False, error_code=e.code, error_message=e.message)
        _log(entry)
        raise


async def cancel_order(account_seq: int, order_id: str) -> OrderOut:
    entry = _base_entry(account_seq, "CANCEL")
    entry.update(order_id=order_id)
    try:
        raw = await get_toss_client().cancel_order(account_seq, order_id)
        parsed = parse_order(raw)
        entry.update(status=parsed.status, success=True)
        _log(entry)
        return parsed
    except TossApiError as e:
        entry.update(success=False, error_code=e.code, error_message=e.message)
        _log(entry)
        raise


async def get_open_orders(account_seq: int, symbol: Optional[str] = None) -> list[OrderOut]:
    raw = await get_toss_client().get_open_orders(account_seq, symbol)
    orders = raw.get("orders", raw) if isinstance(raw, dict) else raw
    return [parse_order(o) for o in (orders or [])]


async def get_order(account_seq: int, order_id: str) -> OrderOut:
    raw = await get_toss_client().get_order(account_seq, order_id)
    return parse_order(raw)


def get_order_log(account_seq: int, limit: int = 50) -> list[dict]:
    try:
        res = (
            get_supabase()
            .table("orders_log")
            .select("*")
            .eq("account_seq", account_seq)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []
