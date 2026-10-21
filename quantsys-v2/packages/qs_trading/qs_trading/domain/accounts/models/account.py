# domain/accounts/models/account.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum

class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    ARCHIVED = "archived"

@dataclass
class Account:
    """账户模型 - 表示用户在系统中的交易账户"""
    account_name: str
    display_name: str
    status: AccountStatus
    initial_capital: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    strategy_name: Optional[str] = None
    account_type: Optional[str] = None
