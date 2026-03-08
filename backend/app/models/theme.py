from pydantic import BaseModel
from typing import List, Optional
from app.models.stock import StockPrice


class Theme(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    stocks: List[str]


class ThemeStrength(BaseModel):
    theme_id: str
    theme_name: str
    avg_change_rate: float
    rising_count: int
    falling_count: int
    total: int


class ThemeDetail(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    strength: ThemeStrength
    stock_prices: List[StockPrice]


class Alert(BaseModel):
    id: str
    target_type: str  # "theme" or "stock"
    target_id: str
    target_name: str
    condition: str  # "above" or "below"
    threshold: float
    is_active: bool = True
    created_at: str


class AlertCreate(BaseModel):
    target_type: str
    target_id: str
    condition: str
    threshold: float


class AlertTriggered(BaseModel):
    alert_id: str
    target_name: str
    current_value: float
    threshold: float
    condition: str
    triggered_at: str
