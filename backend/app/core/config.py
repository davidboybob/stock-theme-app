from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_mock: bool = True
    kis_account_number: str = ""

    @property
    def kis_base_url(self) -> str:
        if self.kis_mock:
            return "https://openapivts.koreainvestment.com:29443"
        return "https://openapi.koreainvestment.com:9443"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
