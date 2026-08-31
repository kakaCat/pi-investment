# domain/accounts/models/balance.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Balance:
    """资金模型 - 表示账户的资金状态"""
    account_name: str
    available_cash: float      # 可用资金
    frozen_cash: float = 0.0   # 冻结资金
    total_value: float = 0.0   # 总资产
    position_value: float = 0.0  # 持仓市值
    peak_value: float = 0.0    # 历史峰值
    cumulative_return: float = 0.0  # 累计收益率
    max_drawdown: float = 0.0  # 最大回撤
    updated_at: Optional[datetime] = None
