from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    naver_base_url: str = "https://polling.finance.naver.com"
    request_timeout: float = 10.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
