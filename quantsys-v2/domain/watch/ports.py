"""
Watch 领域端口（接口定义）

定义 WatchEngine 核心领域的抽象接口，由基础设施层实现。
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from datetime import datetime

from domain.watch.models import WatchRule, RuleHealthReport


class IWatchRuleRepository(ABC):
    """盯盘规则仓储接口"""
    
    @abstractmethod
    def get_all_enabled(self) -> List[WatchRule]:
        """获取所有启用的规则"""
        pass
    
    @abstractmethod
    def get_by_id(self, rule_id: int) -> Optional[WatchRule]:
        """根据 ID 获取规则"""
        pass
    
    @abstractmethod
    def get_by_symbol(self, symbol: str) -> List[WatchRule]:
        """根据股票代码获取规则"""
        pass
    
    @abstractmethod
    def update(self, rule: WatchRule) -> bool:
        """更新规则"""
        pass
    
    @abstractmethod
    def disable(self, rule_id: int, reason: str) -> bool:
        """禁用规则"""
        pass


class ITriggerHistoryRepository(ABC):
    """触发历史仓储接口"""
    
    @abstractmethod
    def count_recent_triggers(self, rule_id: int, window_minutes: int) -> int:
        """统计规则近 window_minutes 分钟内的触发次数"""
        pass
    
    @abstractmethod
    def count_concurrent_triggers(self, symbol: str, window_seconds: int) -> int:
        """统计股票近 window_seconds 秒内的并发触发规则数"""
        pass
    
    @abstractmethod
    def get_last_trigger(self, rule_id: int) -> Optional[datetime]:
        """获取规则最后一次触发时间"""
        pass


class IQuoteProvider(ABC):
    """实时行情端口"""
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[float]:
        """获取股票当前价格"""
        pass
