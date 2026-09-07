"""
类型提示改进 - 核心服务模块

为 strategy_service.py 添加完整类型提示
"""
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from datetime import datetime
import logging

# 类型别名
StrategyName = str
AccountName = str
ConfigDict = Dict[str, Any]

logger = logging.getLogger(__name__)


class StrategyServiceTyped:
    """策略服务 - 类型安全版本

    提供完整的类型提示，提升 IDE 支持和重构安全性
    """

    def __init__(self, repo: Optional['ISimulationRepository'] = None) -> None:
        """初始化策略服务

        Args:
            repo: 模拟仓库接口（可选，用于依赖注入）
        """
        self.config_dir: Path = Path(__file__).parent.parent.parent / 'live_trading' / 'configs' / 'strategies'
        self.repo = repo
        self._configs_cache: Dict[StrategyName, ConfigDict] = {}

    def list_strategies(self) -> List[StrategyName]:
        """列出所有可用策略

        Returns:
            策略名称列表，如 ['v13', 'v14', 'v15']

        Note:
            只返回配置文件存在且账户已注册的策略
        """
        ...

    def get_config(self, strategy_name: StrategyName) -> ConfigDict:
        """获取策略配置

        Args:
            strategy_name: 策略名称（如 'v13', 'v14'）

        Returns:
            策略配置字典，包含 strategy/pool/rebalance 等配置

        Raises:
            ValueError: 策略配置文件不存在

        Note:
            配置会被缓存，重复调用不会重复读取文件
        """
        ...

    def get_account_info(self, strategy_name: StrategyName) -> Dict[str, Union[str, float, int, datetime, None]]:
        """获取策略账户信息

        Args:
            strategy_name: 策略名称

        Returns:
            账户信息字典，包含以下字段：
            - strategy_name: str - 策略名称
            - account_name: str - 账户名称
            - total_value: float - 总资产（元）
            - cash: float - 可用现金（元）
            - position_value: float - 持仓市值（元）
            - positions_count: int - 持仓数量
            - cumulative_return: float - 累计收益率（小数）
            - last_rebalance_date: Optional[datetime] - 最后调仓日期
            - config: Dict - 策略配置摘要

        Raises:
            ValueError: 策略不存在
            DatabaseError: 数据库查询失败
        """
        ...

    def manual_rebalance(
        self,
        strategy_name: StrategyName,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """手动触发调仓

        Args:
            strategy_name: 策略名称
            dry_run: 是否只模拟不实际执行（默认 False）

        Returns:
            调仓结果字典：
            - success: bool - 是否成功
            - message: str - 执行消息
            - actions: List[Dict] - 调仓操作列表
              - action: str - 'buy' 或 'sell'
              - symbol: str - 股票代码
              - shares: int - 股数
              - price: float - 价格
              - amount: float - 金额
            - summary: Dict - 汇总信息
              - total_buy: float - 买入总金额
              - total_sell: float - 卖出总金额
              - net_flow: float - 净流入

        Raises:
            MarketClosedError: 非交易时段
            InsufficientFundsError: 资金不足
            InvalidOrderError: 订单参数错误
        """
        ...

    def daily_check(self, strategy_name: StrategyName) -> Dict[str, Any]:
        """每日例行检查

        检查持仓状态、信号触发、风险指标等

        Args:
            strategy_name: 策略名称

        Returns:
            检查结果字典：
            - strategy_name: str
            - check_time: datetime
            - positions: List[Dict] - 持仓列表
            - signals: List[Dict] - 触发的信号
            - risk_alerts: List[Dict] - 风险告警
            - recommendations: List[str] - 操作建议

        Raises:
            DatabaseError: 数据库查询失败
        """
        ...
