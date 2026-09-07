# domain/accounts/models/balance.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Balance:
    """资金模型 - 表示账户的资金状态

    重构说明（2026-09-01）:
        total_value 改为 @property 计算属性，避免数据不一致风险。
        total_value = available_cash + frozen_cash + position_value
    """
    account_name: str
    available_cash: float      # 可用资金
    frozen_cash: float = 0.0   # 冻结资金
    position_value: float = 0.0  # 持仓市值
    peak_value: float = 0.0    # 历史峰值
    cumulative_return: float = 0.0  # 累计收益率
    max_drawdown: float = 0.0  # 最大回撤
    updated_at: Optional[datetime] = None

    @property
    def total_value(self) -> float:
        """总资产（计算属性）

        Returns:
            可用资金 + 冻结资金 + 持仓市值
        """
        return self.available_cash + self.frozen_cash + self.position_value
