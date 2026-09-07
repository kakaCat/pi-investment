"""
扩展的 Repository Ports 定义

为所有 27 个 Repository 定义接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import polars as pl


# ==================== 已有的核心接口 ====================

class IKlineRepository(ABC):
    """K线数据仓储接口"""
    @abstractmethod
    def get_kline_data(self, symbol: str, start_date: Optional[str] = None,
                       end_date: Optional[str] = None, period: str = 'daily') -> pl.DataFrame:
        pass

class ISignalRepository(ABC):
    """信号仓储接口"""
    @abstractmethod
    def create_signal(self, signal_data: Dict[str, Any]) -> int:
        pass

class IPortfolioRepository(ABC):
    """组合仓储接口"""
    @abstractmethod
    def get_portfolio_history(self, portfolio_name: str, start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class IRiskRepository(ABC):
    """风险仓储接口"""
    @abstractmethod
    def get_risk_metrics(self, symbol: Optional[str] = None, start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class IFactorRepository(ABC):
    """因子仓储接口"""
    @abstractmethod
    def get_factor_data(self, symbol: str, factor_names: Optional[List[str]] = None,
                        start_date: Optional[str] = None, end_date: Optional[str] = None) -> pl.DataFrame:
        pass

class IStrategyRepository(ABC):
    """策略仓储接口"""
    @abstractmethod
    def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        pass


# ==================== 新增接口 ====================

class IStockRepository(ABC):
    """股票基础信息仓储接口"""
    @abstractmethod
    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        pass

class IBacktestRepository(ABC):
    """回测仓储接口"""
    @abstractmethod
    def save_backtest_result(self, result: Dict[str, Any]) -> int:
        pass

class IFinancialRepository(ABC):
    """财务数据仓储接口"""
    @abstractmethod
    def get_financial_data(self, symbol: str, start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> pl.DataFrame:
        pass

class IStockPoolRepository(ABC):
    """股票池仓储接口"""
    @abstractmethod
    def get_pool(self, pool_id: int) -> Optional[Dict[str, Any]]:
        pass

class IPositionRepository(ABC):
    """持仓仓储接口"""
    @abstractmethod
    def get_positions(self, portfolio_name: str, trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class IRiskConfigRepository(ABC):
    """风险配置仓储接口"""
    @abstractmethod
    def get_risk_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        pass

class IStrategyPerformanceRepository(ABC):
    """策略绩效仓储接口"""
    @abstractmethod
    def get_performance(self, strategy_id: int, start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class IFundFlowRepository(ABC):
    """资金流向仓储接口"""
    @abstractmethod
    def get_fund_flow(self, symbol: str, start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class IMarketStyleRepository(ABC):
    """市场风格仓储接口"""
    @abstractmethod
    def get_market_style(self, trade_date: str) -> Optional[Dict[str, Any]]:
        pass

class IDataQualityRepository(ABC):
    """数据质量仓储接口"""
    @abstractmethod
    def log_quality_issue(self, issue: Dict[str, Any]) -> int:
        pass

class IMlModelRepository(ABC):
    """机器学习模型仓储接口"""
    @abstractmethod
    def get_model(self, model_id: int) -> Optional[Dict[str, Any]]:
        pass

class IStrategyCircuitBreakerRepository(ABC):
    """策略熔断仓储接口"""
    @abstractmethod
    def check_circuit_breaker(self, strategy_id: int) -> bool:
        pass

class IStrategyWeightRepository(ABC):
    """策略权重仓储接口"""
    @abstractmethod
    def get_weights(self, portfolio_name: str, trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class ITraceabilityRepository(ABC):
    """可追溯性仓储接口"""
    @abstractmethod
    def log_operation(self, operation: Dict[str, Any]) -> int:
        pass

class IAgentIntelligenceRepository(ABC):
    """智能体决策仓储接口"""
    @abstractmethod
    def save_decision(self, decision: Dict[str, Any]) -> int:
        pass

class ISignalExecutionLogRepository(ABC):
    """信号执行日志仓储接口"""
    @abstractmethod
    def log_execution(self, execution: Dict[str, Any]) -> int:
        pass

class ISignalExecutionRepository(ABC):
    """信号执行仓储接口"""
    @abstractmethod
    def get_execution(self, execution_id: int) -> Optional[Dict[str, Any]]:
        pass

class ISimulationRepository(ABC):
    """模拟交易仓储接口"""
    @abstractmethod
    def save_simulation_result(self, result: Dict[str, Any]) -> int:
        pass

class IAsyncKlineRepository(ABC):
    """异步K线仓储接口"""
    @abstractmethod
    async def get_kline_data_async(self, symbol: str, start_date: Optional[str] = None,
                                    end_date: Optional[str] = None) -> pl.DataFrame:
        pass

class IAsyncFactorRepository(ABC):
    """异步因子仓储接口"""
    @abstractmethod
    async def get_factor_data_async(self, symbol: str, factor_names: Optional[List[str]] = None) -> pl.DataFrame:
        pass

class ISchedulerConfigRepository(ABC):
    """调度器配置仓储接口"""
    @abstractmethod
    def get_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        pass

class ISchedulerRepository(ABC):
    """调度器仓储接口"""
    @abstractmethod
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        pass

class IAgentKnowledgeRepository(ABC):
    """Agent 知识库仓储接口"""
    @abstractmethod
    def save_knowledge(self, knowledge: Dict[str, Any]) -> int:
        pass

class IAgentDecisionRepository(ABC):
    """Agent 决策仓储接口"""
    @abstractmethod
    def save_decision(self, decision: Dict[str, Any]) -> int:
        pass

class IHeatmapRepository(ABC):
    """热力图仓储接口"""
    @abstractmethod
    def get_heatmap_data(self, date: str) -> Optional[Dict[str, Any]]:
        pass

class IOrderRepository(ABC):
    """订单仓储接口"""
    @abstractmethod
    def get_orders(self, portfolio_name: str, trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

class IDecisionRepository(ABC):
    """决策仓储接口"""
    @abstractmethod
    def save_decision(self, decision: Dict[str, Any]) -> int:
        pass

class IPoolRepository(ABC):
    """股票池仓储接口（通用）"""
    @abstractmethod
    def get_pool_members(self, pool_name: str) -> List[str]:
        pass

class IConditionRuleRepository(ABC):
    """条件规则仓储接口"""
    @abstractmethod
    def get_active_rules(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_rule_status(self, rule_id: int, status: str) -> None:
        pass

class IConditionResultRepository(ABC):
    """条件结果仓储接口"""
    @abstractmethod
    def save_result(self, result: Dict[str, Any]) -> int:
        pass

    @abstractmethod
    def get_recent_results(self, rule_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        pass

class IPoolChangeLogRepository(ABC):
    """股票池变更日志仓储接口"""
    @abstractmethod
    def log_change(self, pool_name: str, change_type: str, symbols: List[str], reason: str) -> int:
        pass

    @abstractmethod
    def get_changes(self, pool_name: Optional[str] = None, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        pass


class IWatchRuleRepository(ABC):
    """盯盘规则仓储接口"""
    @abstractmethod
    def create_rule(self, symbol: str, conditions: Dict[str, Any], context: Optional[str] = None,
                    cost_price: Optional[float] = None, active_window: Optional[Dict] = None,
                    expires_at: Optional[datetime] = None, created_by: str = 'agent') -> Any:
        """创建盯盘规则"""
        pass

    @abstractmethod
    def list_enabled(self) -> List[Any]:
        """获取所有启用且未过期的规则"""
        pass

    @abstractmethod
    def list_rules(self, symbol: Optional[str] = None, enabled: Optional[bool] = None) -> List[Any]:
        """列出规则（可按股票和启用状态过滤）"""
        pass

    @abstractmethod
    def get_by_id(self, rule_id: int) -> Optional[Any]:
        """根据ID获取规则"""
        pass

    @abstractmethod
    def update_fields(self, rule_id: int, **fields) -> Optional[Any]:
        """更新规则字段"""
        pass


class IEvolutionFitnessRepository(ABC):
    """进化适应度仓储接口"""
    @abstractmethod
    def upsert_fitness(self, account_name: str, window_end: date, up_capture: Optional[float],
                      down_capture: Optional[float], fitness: Optional[float],
                      up_days: int, down_days: int, status: str, window_days: int = 20) -> None:
        """插入或更新适应度记录"""
        pass

    @abstractmethod
    def get_leaderboard(self, window_end: date, window_days: int = 20,
                       include_non_ok: bool = False) -> List[Dict[str, Any]]:
        """获取适应度排行榜"""
        pass

    @abstractmethod
    def get_latest_window_end(self, window_days: int = 20) -> Optional[date]:
        """获取最新窗口结束日期"""
        pass


class IMemoryRepository(ABC):
    """记忆仓储接口（用于 domain.memory）"""

    @abstractmethod
    def create(self, entry) -> Dict[str, Any]:
        """创建新记忆条目
        
        Args:
            entry: MemoryEntry 领域对象
            
        Returns:
            创建的记忆条目字典
        """
        pass

    @abstractmethod
    def list_filtered(self, kind: Optional[str] = None, max_rows: int = 100) -> List[Dict[str, Any]]:
        """列出过滤后的记忆条目
        
        Args:
            kind: 记忆类型过滤（可选）
            max_rows: 最大返回行数
            
        Returns:
            记忆条目列表
        """
        pass

    @abstractmethod
    def get_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取记忆条目
        
        Args:
            entry_id: 记忆条目 ID
            
        Returns:
            记忆条目字典或 None
        """
        pass
