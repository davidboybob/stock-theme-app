from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    naver_base_url: str = "https://polling.finance.naver.com"
    request_timeout: float = 10.0

    # 토스증권 Open API
    toss_base_url: str = "https://openapi.tossinvest.com"
    toss_client_id: str = ""
    toss_client_secret: str = ""

    # 트레이딩 기능 게이트 (공개 배포에서는 반드시 false)
    trading_enabled: bool = False

    # 자동매매 봇 (Phase 3)
    # 실주문 전환은 이 값이 true일 때만 가능 — false면 UI 토글과 무관하게 dry-run 강제
    bot_live_trading: bool = False
    bot_interval_minutes: int = 5
    bot_theme_threshold: float = 2.0     # 테마 평균 등락률 매수 임계 (%)
    bot_order_budget: int = 100000       # live 시 종목당 주문 예산 (원)
    bot_max_signals_per_day: int = 20

    # 자동매매 안전장치 (Phase 4) — dry-run에서도 체크해 시그널에 차단 사유를 남긴다
    bot_max_order_amount: int = 200000        # 주문 1건 금액 상한 (원)
    bot_daily_max_order_amount: int = 500000  # 일일 주문 금액 합계 상한 (원)
    bot_daily_loss_limit: int = 50000         # 계좌 일 손실 한도 (원) — 초과 시 자동 정지 (live 전용)
    bot_max_consecutive_failures: int = 3     # 연속 주문 실패 시 자동 정지

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
