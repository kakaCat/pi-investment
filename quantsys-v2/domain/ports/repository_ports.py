"""
Repository Ports (接口定义)

Domain 层定义的 Repository 接口
Adapters 层的 Repository 实现必须符合这些接口

符合依赖倒置原则 (DIP)：
- 高层模块 (Domain) 定义接口
- 低层模块 (Adapters) 实现接口
- 双方都依赖抽象，不依赖具体
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import polars as pl


class IKlineRepository(ABC):
    """K线数据仓储接口"""

    @abstractmethod
    def get_kline_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = 'daily'
    ) -> pl.DataFrame:
        """获取K线数据"""
        pass

    @abstractmethod
    def batch_get_kline(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        period: str = 'daily'
    ) -> Dict[str, pl.DataFrame]:
        """批量获取K线数据"""
        pass

    @abstractmethod
    def save_kline_data(self, df: pl.DataFrame) -> int:
        """保存K线数据"""
        pass


class ISignalRepository(ABC):
    """信号仓储接口"""

    @abstractmethod
    def create_signal(self, signal_data: Dict[str, Any]) -> int:
        """创建信号"""
        pass

    @abstractmethod
    def get_signals(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        signal_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取信号列表"""
        pass


class IPortfolioRepository(ABC):
    """组合仓储接口"""

    @abstractmethod
    def get_portfolio_history(
        self,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取组合历史"""
        pass

    @abstractmethod
    def save_portfolio_snapshot(
        self,
        portfolio_name: str,
        snapshot_data: Dict[str, Any]
    ) -> int:
        """保存组合快照"""
        pass


class IRiskRepository(ABC):
    """风险仓储接口"""

    @abstractmethod
    def get_risk_metrics(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取风险指标"""
        pass

    @abstractmethod
    def save_risk_metrics(self, metrics: Dict[str, Any]) -> int:
        """保存风险指标"""
        pass


class IFactorRepository(ABC):
    """因子仓储接口"""

    @abstractmethod
    def get_factor_data(
        self,
        symbol: str,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pl.DataFrame:
        """获取因子数据"""
        pass

    @abstractmethod
    def batch_get_factors(
        self,
        symbols: List[str],
        factor_names: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, pl.DataFrame]:
        """批量获取因子数据"""
        pass

    @abstractmethod
    def save_factor_data(self, df: pl.DataFrame) -> int:
        """保存因子数据"""
        pass


class IStrategyRepository(ABC):
    """策略仓储接口"""

    @abstractmethod
    def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """获取策略"""
        pass

    @abstractmethod
    def list_strategies(
        self,
        source: Optional[str] = None,
        code_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """列出策略"""
        pass

    @abstractmethod
    def create_strategy(self, strategy_data: Dict[str, Any]) -> int:
        """创建策略"""
        pass

    @abstractmethod
    def update_strategy(self, strategy_id: int, updates: Dict[str, Any]) -> bool:
        """更新策略"""
        pass


class ISchedulerRepository(ABC):
    """调度任务仓储接口"""

    # ── Task CRUD ──

    @abstractmethod
    def add_task(
        self,
        name: str,
        cron_expression: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
    ) -> int:
        """注册新的定时任务，返回 task id"""
        pass

    @abstractmethod
    def remove_task(self, task_id: int) -> bool:
        """删除任务"""
        pass

    @abstractmethod
    def update_task(self, task_id: int, **kwargs) -> bool:
        """更新任务字段（name/description/cron_expression/command/params/is_enabled）"""
        pass

    @abstractmethod
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据 id 获取任务"""
        pass

    @abstractmethod
    def get_task_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据 name 获取任务"""
        pass

    @abstractmethod
    def list_tasks(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """列出所有任务"""
        pass

    @abstractmethod
    def count_tasks(self, enabled_only: bool = False) -> int:
        """统计任务数"""
        pass

    @abstractmethod
    def enable_task(self, task_id: int) -> bool:
        """启用任务"""
        pass

    @abstractmethod
    def disable_task(self, task_id: int) -> bool:
        """禁用任务"""
        pass

    # ── Run Lifecycle ──

    @abstractmethod
    def create_run(self, task_id: int) -> int:
        """创建执行记录（status='running'），返回 run id"""
        pass

    @abstractmethod
    def complete_run(
        self,
        run_id: int,
        success: bool = True,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """完成执行记录，同时更新 task 的 last_status/next_run_at"""
        pass

    @abstractmethod
    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """获取单条执行记录"""
        pass

    @abstractmethod
    def list_runs(
        self,
        task_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        statuses: Optional[List[str]] = None,
        date_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出执行历史"""
        pass

    @abstractmethod
    def count_runs(
        self,
        task_id: Optional[int] = None,
        statuses: Optional[List[str]] = None,
        date_filter: Optional[str] = None,
    ) -> int:
        """统计执行记录数"""
        pass

    # ── Health Check ──

    @abstractmethod
    def find_zombie_runs(self, threshold_hours: int = 1) -> List[Dict[str, Any]]:
        """查找僵尸 running 任务"""
        pass

    @abstractmethod
    def find_missed_tasks(self, threshold_hours: int = 24) -> List[Dict[str, Any]]:
        """查找超过阈值未执行的任务"""
        pass

    @abstractmethod
    def find_high_failure_tasks(
        self, days: int = 7, min_runs: int = 3, fail_rate_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """查找高失败率任务"""
        pass

    @abstractmethod
    def count_enabled_tasks(self) -> int:
        """统计启用中的任务数"""
        pass
