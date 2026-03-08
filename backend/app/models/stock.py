from pydantic import BaseModel
from typing import Optional


class StockPrice(BaseModel):
    code: str
    name: str
    current_price: int
    change_price: int
    change_rate: float
    volume: int
    high_price: int
    low_price: int
    open_price: int


class StockDetail(BaseModel):
    code: str
    name: str
    market: str
    sector: str
    per: Optional[float] = None
    pbr: Optional[float] = None
    market_cap: Optional[int] = None


class IndexPrice(BaseModel):
    code: str
    name: str
    current_value: float
    change_value: float
    change_rate: float
