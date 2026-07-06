from __future__ import annotations
import asyncio
import uuid
from datetime import datetime
from app.brokers.base import BaseBroker
from app.db import get_supabase

class MockBroker(BaseBroker):
    """모의투자 브로커 - Supabase trading_config.paper_balance 기반"""

    def _get_balance_sync(self) -> int:
        sb = get_supabase()
        res = sb.table("trading_config").select("paper_balance").limit(1).execute()
        if res.data:
            return res.data[0]["paper_balance"]
        return 10_000_000

    def _update_balance_sync(self, new_balance: int) -> None:
        sb = get_supabase()
        res = sb.table("trading_config").select("id").limit(1).execute()
        if res.data:
            sb.table("trading_config").update({"paper_balance": new_balance}).eq("id", res.data[0]["id"]).execute()

    def _insert_position_sync(self, code: str, name: str, quantity: int, entry_price: int, stop_loss_price: int, take_profit_price: int) -> None:
        sb = get_supabase()
        sb.table("positions").insert({
            "id": str(uuid.uuid4()),
            "mode": "paper",
            "stock_code": code,
            "stock_name": name,
            "quantity": quantity,
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "entered_at": datetime.now().isoformat(),
        }).execute()

    def _get_position_sync(self, code: str) -> dict | None:
        sb = get_supabase()
        res = sb.table("positions").select("*").eq("stock_code", code).eq("mode", "paper").limit(1).execute()
        return res.data[0] if res.data else None

    def _delete_position_sync(self, position_id: str) -> None:
        sb = get_supabase()
        sb.table("positions").delete().eq("id", position_id).execute()

    def _insert_trade_history_sync(self, code: str, name: str, signal_type: str, price: int, quantity: int, reason: str, profit_loss: int | None) -> None:
        sb = get_supabase()
        sb.table("trade_history").insert({
            "mode": "paper",
            "stock_code": code,
            "stock_name": name,
            "signal_type": signal_type,
            "price": price,
            "quantity": quantity,
            "reason": reason,
            "profit_loss": profit_loss,
            "executed_at": datetime.now().isoformat(),
        }).execute()

    async def get_balance(self) -> int:
        return await asyncio.to_thread(self._get_balance_sync)

    async def buy(self, code: str, name: str, price: int, quantity: int, stop_loss_price: int = 0, take_profit_price: int = 0, reason: str = "golden_cross") -> dict:
        balance = await asyncio.to_thread(self._get_balance_sync)
        cost = price * quantity
        if balance < cost:
            return {"success": False, "order_id": "", "message": f"잔고 부족: {balance:,}원 < {cost:,}원"}

        new_balance = balance - cost
        await asyncio.to_thread(self._update_balance_sync, new_balance)
        await asyncio.to_thread(
            self._insert_position_sync, code, name, quantity, price, stop_loss_price, take_profit_price
        )
        await asyncio.to_thread(
            self._insert_trade_history_sync, code, name, "BUY", price, quantity, reason, None
        )
        return {"success": True, "order_id": str(uuid.uuid4()), "message": f"매수 완료: {name} {quantity}주 @{price:,}원"}

    async def sell(self, code: str, name: str, price: int, quantity: int, reason: str = "dead_cross") -> dict:
        position = await asyncio.to_thread(self._get_position_sync, code)
        if not position:
            return {"success": False, "order_id": "", "message": f"보유 포지션 없음: {name}"}

        proceeds = price * quantity
        profit_loss = proceeds - (position["entry_price"] * quantity)
        balance = await asyncio.to_thread(self._get_balance_sync)
        new_balance = balance + proceeds

        await asyncio.to_thread(self._update_balance_sync, new_balance)
        await asyncio.to_thread(self._delete_position_sync, position["id"])
        await asyncio.to_thread(
            self._insert_trade_history_sync, code, name, "SELL", price, quantity, reason, profit_loss
        )
        return {"success": True, "order_id": str(uuid.uuid4()), "message": f"매도 완료: {name} {quantity}주 @{price:,}원, 손익 {profit_loss:+,}원"}

mock_broker = MockBroker()
