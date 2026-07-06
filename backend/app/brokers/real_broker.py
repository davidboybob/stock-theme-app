from app.brokers.base import BaseBroker

class RealBroker(BaseBroker):
    """실거래 브로커 - 증권사 API 연동 시 구현 (현재 미연동)"""

    async def buy(self, code: str, name: str, price: int, quantity: int, **kwargs) -> dict:
        raise NotImplementedError("증권사 API가 아직 연동되지 않았습니다. 모의투자 모드를 사용하세요.")

    async def sell(self, code: str, name: str, price: int, quantity: int, **kwargs) -> dict:
        raise NotImplementedError("증권사 API가 아직 연동되지 않았습니다. 모의투자 모드를 사용하세요.")

    async def get_balance(self) -> int:
        raise NotImplementedError("증권사 API가 아직 연동되지 않았습니다. 모의투자 모드를 사용하세요.")

real_broker = RealBroker()
