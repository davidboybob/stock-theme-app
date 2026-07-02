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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
