"""주문 관련 Pydantic 모델."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class OrderCreateIn(BaseModel):
    """프론트 → 백엔드 주문 생성 요청 (KRX 수량 기반)."""

    symbol: str = Field(..., description="KRX 6자리 종목코드 (예: 005930)")
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET"] = "LIMIT"
    quantity: int = Field(..., gt=0)
    price: Optional[int] = Field(None, gt=0, description="LIMIT 주문 시 필수 (원)")
    confirm_high_value: bool = False
    client_order_id: Optional[str] = Field(None, max_length=36)

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, v: str) -> str:
        if not (len(v) == 6 and v.isdigit()):
            raise ValueError("KRX 종목코드는 6자리 숫자여야 합니다")
        return v

    def to_toss_payload(self) -> dict:
        payload: dict = {
            "symbol": self.symbol,
            "side": self.side,
            "orderType": self.order_type,
            "quantity": self.quantity,
            "confirmHighValueOrder": self.confirm_high_value,
        }
        if self.order_type == "LIMIT":
            if self.price is None:
                raise ValueError("LIMIT 주문에는 price가 필수입니다")
            payload["price"] = self.price
        if self.client_order_id:
            payload["clientOrderId"] = self.client_order_id
        return payload


class OrderModifyIn(BaseModel):
    quantity: Optional[int] = Field(None, gt=0)
    price: Optional[int] = Field(None, gt=0)

    def to_toss_payload(self) -> dict:
        payload: dict = {}
        if self.quantity is not None:
            payload["quantity"] = self.quantity
        if self.price is not None:
            payload["price"] = self.price
        return payload


class OrderOut(BaseModel):
    """토스 주문 객체 정규화."""

    order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    price: Optional[float] = None
    quantity: float = 0
    filled_quantity: float = 0
    currency: str = "KRW"
    ordered_at: Optional[str] = None
    canceled_at: Optional[str] = None
    raw_execution: Optional[dict[str, Any]] = None


def parse_order(raw: dict) -> OrderOut:
    execution = raw.get("execution") or {}
    return OrderOut(
        order_id=raw.get("orderId", ""),
        symbol=raw.get("symbol", ""),
        side=str(raw.get("side", "")),
        order_type=str(raw.get("orderType", "")),
        status=str(raw.get("status", "")),
        price=raw.get("price"),
        quantity=float(raw.get("quantity", 0) or 0),
        filled_quantity=float(execution.get("filledQuantity", 0) or 0),
        currency=str(raw.get("currency", "KRW")),
        ordered_at=raw.get("orderedAt"),
        canceled_at=raw.get("canceledAt"),
        raw_execution=execution or None,
    )
