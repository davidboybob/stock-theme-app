"""토스증권 계좌·자산 Pydantic 모델."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class Account(BaseModel):
    account_no: str
    account_seq: int
    account_type: str


class HoldingItem(BaseModel):
    symbol: str
    name: str
    market_country: str
    currency: str
    quantity: float
    last_price: float
    average_purchase_price: float
    market_value: Optional[dict[str, Any]] = None
    profit_loss: Optional[dict[str, Any]] = None
    daily_profit_loss: Optional[dict[str, Any]] = None


class PortfolioSummary(BaseModel):
    """보유 주식 요약. 원본 통화별 합산 구조(dict)를 그대로 전달한다."""

    total_purchase_amount: Optional[dict[str, Any]] = None
    market_value: Optional[dict[str, Any]] = None
    profit_loss: Optional[dict[str, Any]] = None
    daily_profit_loss: Optional[dict[str, Any]] = None
    items: list[HoldingItem] = []


def parse_account(raw: dict) -> Account:
    return Account(
        account_no=raw.get("accountNo", ""),
        account_seq=raw.get("accountSeq", 0),
        account_type=raw.get("accountType", ""),
    )


def parse_holdings(raw: dict) -> PortfolioSummary:
    items = [
        HoldingItem(
            symbol=item.get("symbol", ""),
            name=item.get("name", ""),
            market_country=str(item.get("marketCountry", "")),
            currency=str(item.get("currency", "")),
            quantity=float(item.get("quantity", 0) or 0),
            last_price=float(item.get("lastPrice", 0) or 0),
            average_purchase_price=float(item.get("averagePurchasePrice", 0) or 0),
            market_value=item.get("marketValue"),
            profit_loss=item.get("profitLoss"),
            daily_profit_loss=item.get("dailyProfitLoss"),
        )
        for item in raw.get("items", [])
    ]
    return PortfolioSummary(
        total_purchase_amount=raw.get("totalPurchaseAmount"),
        market_value=raw.get("marketValue"),
        profit_loss=raw.get("profitLoss"),
        daily_profit_loss=raw.get("dailyProfitLoss"),
        items=items,
    )
