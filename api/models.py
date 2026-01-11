"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    TRADE = "TRADE"
    OPTION_OPEN = "OPTION_OPEN"
    OPTION_CLOSE = "OPTION_CLOSE"
    OPTION_EXPIRE = "OPTION_EXPIRE"
    OPTION_ASSIGN = "OPTION_ASSIGN"
    DIVIDEND = "DIVIDEND"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    PRICE_UPDATE = "PRICE_UPDATE"
    NOTE = "NOTE"


class TradeRequest(BaseModel):
    action: str = Field(..., pattern="^(BUY|SELL|buy|sell)$")
    ticker: str
    shares: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    gain_loss: float = 0
    reason: str = ""
    notes: str = ""


class OptionOpenRequest(BaseModel):
    ticker: str
    strategy: str = "Secured Put"
    strike: float = Field(..., gt=0)
    expiration: str  # YYYY-MM-DD
    contracts: int = Field(1, gt=0)
    premium: float = Field(..., gt=0)
    reason: str = ""


class OptionCloseRequest(BaseModel):
    event_id: Optional[int] = None  # Option's original event_id
    position_id: Optional[str] = None  # Option's UUID (preferred)
    close_cost: float = 0
    close_type: str = "CLOSE"  # CLOSE, EXPIRE, ASSIGN
    reason: str = ""


class CashRequest(BaseModel):
    action: str = Field(..., pattern="^(DEPOSIT|WITHDRAWAL|deposit|withdrawal)$")
    amount: float = Field(..., gt=0)
    description: str = ""
    reason: str = ""


class Holding(BaseModel):
    ticker: str
    shares: int
    current_price: float = 0
    market_value: float = 0
    cost_basis: float = 0
    avg_cost: float = 0
    unrealized_gain: float = 0
    unrealized_gain_pct: float = 0
    allocation_pct: float = 0


class ActiveOption(BaseModel):
    event_id: int
    position_id: str = ""  # UUID for correlation
    ticker: str
    strategy: str
    strike: float
    expiration: str
    contracts: int
    premium: float
    days_to_expiry: int = 0


class IncomeBreakdown(BaseModel):
    trading_gains: float = 0
    option_income: float = 0
    dividends: float = 0
    total: float = 0
    goal: float = 30000
    progress_pct: float = 0


class PortfolioState(BaseModel):
    as_of: str
    cash: float
    portfolio_value: float
    total_value: float
    holdings: List[Holding]
    active_options: List[ActiveOption]
    income: IncomeBreakdown
    events_processed: int = 0


class ApiResponse(BaseModel):
    success: bool
    message: str = ""
    event_id: Optional[int] = None
    position_id: Optional[str] = None  # For option positions
    data: Optional[Dict[str, Any]] = None
