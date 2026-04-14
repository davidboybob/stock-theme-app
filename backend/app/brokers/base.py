from abc import ABC, abstractmethod

class BaseBroker(ABC):
    """증권사 API 추상화 인터페이스. KIS/키움 등 실제 API 연동 시 이 클래스를 상속."""

    @abstractmethod
    async def buy(self, code: str, name: str, price: int, quantity: int) -> dict:
        """매수 주문. returns {"success": bool, "order_id": str, "message": str}"""
        ...

    @abstractmethod
    async def sell(self, code: str, name: str, price: int, quantity: int) -> dict:
        """매도 주문. returns {"success": bool, "order_id": str, "message": str}"""
        ...

    @abstractmethod
    async def get_balance(self) -> int:
        """현재 사용 가능 잔고 반환 (원)"""
        ...
