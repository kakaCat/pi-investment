"""
实盘监控模块 - Live Monitor

实时监控交易执行情况，检测异常并触发告警。

监控内容:
1. 信号延迟 - 从信号生成到执行的时间
2. 价格偏差 - 预期价格与实际成交价的偏差
3. 策略漂移 - 策略表现是否偏离历史基线
4. 执行质量 - 成交率、滑点等

使用示例:
    monitor = LiveMonitor(config)

    # 检查信号延迟
    monitor.check_signal_delay(signal_time, execution_time)

    # 检查价格偏差
    monitor.check_price_deviation(expected_price, actual_price)

    # 检查策略漂移
    monitor.check_strategy_drift(strategy_id, recent_performance)
"""

from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """监控配置"""
    # 信号延迟阈值
    signal_delay_warn_seconds: float = 5.0      # 5秒预警
    signal_delay_critical_seconds: float = 15.0  # 15秒严重

    # 价格偏差阈值
    price_deviation_warn: float = 0.003         # 0.3%预警
    price_deviation_critical: float = 0.008     # 0.8%严重

    # 策略漂移阈值
    drift_rolling_days: int = 20                # 滚动窗口20天
    win_rate_drop_warn: float = 0.08            # 胜率下降8%预警
    profit_loss_ratio_drop_warn: float = 0.2    # 盈亏比下降20%预警
    max_drawdown_expansion_warn: float = 0.3    # 回撤扩大30%预警

    # 执行质量阈值
    fill_rate_warn: float = 0.8                 # 成交率低于80%预警
    slippage_warn: float = 0.002                # 滑点超过0.2%预警

    # 告警动作
    auto_reduce_position_on_warn: bool = True   # 预警时自动降仓
    auto_pause_on_critical: bool = True         # 严重时自动暂停
    reduce_position_pct: float = 0.5            # 降仓比例50%


@dataclass
class Alert:
    """告警事件"""
    timestamp: datetime
    alert_type: str  # 'signal_delay', 'price_deviation', 'strategy_drift', 'execution_quality'
    severity: str    # 'WARN', 'CRITICAL'
    strategy_id: Optional[str]
    message: str
    current_value: float
    threshold: float
    metadata: Dict = field(default_factory=dict)


class LiveMonitor:
    """
    实盘监控器

    实时监控交易执行情况，检测异常并触发告警。
    """

    def __init__(
        self,
        config: Optional[MonitorConfig] = None,
        alert_callback: Optional[Callable[[Alert], None]] = None
    ):
        """
        初始化实盘监控器

        Args:
            config: 监控配置
            alert_callback: 告警回调函数
        """
        self.config = config or MonitorConfig()
        self.alert_callback = alert_callback

        # 告警记录
        self.alerts: List[Alert] = []
        self.alert_count_by_type = defaultdict(int)
        self.alert_count_by_strategy = defaultdict(int)

        # 策略基线（用于漂移检测）
        self.strategy_baselines: Dict[str, Dict] = {}

        # 最近表现（滚动窗口）
        self.recent_trades: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )

        # 执行统计
        self.execution_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_signals': 0,
            'filled_signals': 0,
            'total_slippage': 0.0,
            'total_delay': 0.0
        })

        # 暂停状态
        self.paused_strategies: set = set()

    def check_signal_delay(
        self,
        signal_time: datetime,
        execution_time: datetime,
        strategy_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Alert]]:
        """
        检查信号延迟

        Args:
            signal_time: 信号生成时间
            execution_time: 执行时间
            strategy_id: 策略ID

        Returns:
            (has_alert, severity, alert)
        """
        delay_seconds = (execution_time - signal_time).total_seconds()

        # 更新统计
        if strategy_id:
            stats = self.execution_stats[strategy_id]
            stats['total_signals'] += 1
            stats['total_delay'] += delay_seconds

        # 检查阈值
        if delay_seconds >= self.config.signal_delay_critical_seconds:
            alert = self._create_alert(
                alert_type='signal_delay',
                severity='CRITICAL',
                strategy_id=strategy_id,
                message=f'信号延迟 {delay_seconds:.1f}秒 (严重)',
                current_value=delay_seconds,
                threshold=self.config.signal_delay_critical_seconds,
                metadata={'signal_time': signal_time, 'execution_time': execution_time}
            )
            self._handle_alert(alert)
            return True, 'CRITICAL', alert

        elif delay_seconds >= self.config.signal_delay_warn_seconds:
            alert = self._create_alert(
                alert_type='signal_delay',
                severity='WARN',
                strategy_id=strategy_id,
                message=f'信号延迟 {delay_seconds:.1f}秒 (预警)',
                current_value=delay_seconds,
                threshold=self.config.signal_delay_warn_seconds,
                metadata={'signal_time': signal_time, 'execution_time': execution_time}
            )
            self._handle_alert(alert)
            return True, 'WARN', alert

        return False, None, None

    def check_price_deviation(
        self,
        expected_price: float,
        actual_price: float,
        symbol: str,
        strategy_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Alert]]:
        """
        检查价格偏差

        Args:
            expected_price: 预期价格
            actual_price: 实际成交价
            symbol: 股票代码
            strategy_id: 策略ID

        Returns:
            (has_alert, severity, alert)
        """
        if expected_price == 0:
            return False, None, None

        deviation = abs(actual_price - expected_price) / expected_price

        # 更新统计
        if strategy_id:
            stats = self.execution_stats[strategy_id]
            stats['filled_signals'] += 1
            stats['total_slippage'] += deviation

        # 检查阈值
        if deviation >= self.config.price_deviation_critical:
            alert = self._create_alert(
                alert_type='price_deviation',
                severity='CRITICAL',
                strategy_id=strategy_id,
                message=f'{symbol} 价格偏差 {deviation:.2%} (严重)',
                current_value=deviation,
                threshold=self.config.price_deviation_critical,
                metadata={
                    'symbol': symbol,
                    'expected_price': expected_price,
                    'actual_price': actual_price
                }
            )
            self._handle_alert(alert)
            return True, 'CRITICAL', alert

        elif deviation >= self.config.price_deviation_warn:
            alert = self._create_alert(
                alert_type='price_deviation',
                severity='WARN',
                strategy_id=strategy_id,
                message=f'{symbol} 价格偏差 {deviation:.2%} (预警)',
                current_value=deviation,
                threshold=self.config.price_deviation_warn,
                metadata={
                    'symbol': symbol,
                    'expected_price': expected_price,
                    'actual_price': actual_price
                }
            )
            self._handle_alert(alert)
            return True, 'WARN', alert

        return False, None, None

    def check_strategy_drift(
        self,
        strategy_id: str,
        recent_performance: Dict
    ) -> Tuple[bool, Optional[str], Optional[Alert]]:
        """
        检查策略漂移

        对比最近表现与历史基线，检测策略是否失效。

        Args:
            strategy_id: 策略ID
            recent_performance: 最近表现指标
                {
                    'win_rate': 0.6,
                    'profit_loss_ratio': 1.5,
                    'max_drawdown': 0.15
                }

        Returns:
            (has_alert, severity, alert)
        """
        # 获取基线
        if strategy_id not in self.strategy_baselines:
            # 首次检查，设置基线
            self.strategy_baselines[strategy_id] = recent_performance.copy()
            return False, None, None

        baseline = self.strategy_baselines[strategy_id]

        # 检查胜率下降
        if 'win_rate' in recent_performance and 'win_rate' in baseline:
            win_rate_drop = baseline['win_rate'] - recent_performance['win_rate']

            if win_rate_drop >= self.config.win_rate_drop_warn:
                alert = self._create_alert(
                    alert_type='strategy_drift',
                    severity='WARN',
                    strategy_id=strategy_id,
                    message=f'策略 {strategy_id} 胜率下降 {win_rate_drop:.2%}',
                    current_value=recent_performance['win_rate'],
                    threshold=baseline['win_rate'] - self.config.win_rate_drop_warn,
                    metadata={
                        'baseline_win_rate': baseline['win_rate'],
                        'current_win_rate': recent_performance['win_rate']
                    }
                )
                self._handle_alert(alert)
                return True, 'WARN', alert

        # 检查盈亏比下降
        if 'profit_loss_ratio' in recent_performance and 'profit_loss_ratio' in baseline:
            if baseline['profit_loss_ratio'] > 0:
                pl_ratio_drop = (baseline['profit_loss_ratio'] - recent_performance['profit_loss_ratio']) / baseline['profit_loss_ratio']

                if pl_ratio_drop >= self.config.profit_loss_ratio_drop_warn:
                    alert = self._create_alert(
                        alert_type='strategy_drift',
                        severity='WARN',
                        strategy_id=strategy_id,
                        message=f'策略 {strategy_id} 盈亏比下降 {pl_ratio_drop:.2%}',
                        current_value=recent_performance['profit_loss_ratio'],
                        threshold=baseline['profit_loss_ratio'] * (1 - self.config.profit_loss_ratio_drop_warn),
                        metadata={
                            'baseline_pl_ratio': baseline['profit_loss_ratio'],
                            'current_pl_ratio': recent_performance['profit_loss_ratio']
                        }
                    )
                    self._handle_alert(alert)
                    return True, 'WARN', alert

        # 检查回撤扩大
        if 'max_drawdown' in recent_performance and 'max_drawdown' in baseline:
            if baseline['max_drawdown'] > 0:
                dd_expansion = (recent_performance['max_drawdown'] - baseline['max_drawdown']) / baseline['max_drawdown']

                if dd_expansion >= self.config.max_drawdown_expansion_warn:
                    alert = self._create_alert(
                        alert_type='strategy_drift',
                        severity='WARN',
                        strategy_id=strategy_id,
                        message=f'策略 {strategy_id} 回撤扩大 {dd_expansion:.2%}',
                        current_value=recent_performance['max_drawdown'],
                        threshold=baseline['max_drawdown'] * (1 + self.config.max_drawdown_expansion_warn),
                        metadata={
                            'baseline_drawdown': baseline['max_drawdown'],
                            'current_drawdown': recent_performance['max_drawdown']
                        }
                    )
                    self._handle_alert(alert)
                    return True, 'WARN', alert

        return False, None, None

    def update_strategy_baseline(self, strategy_id: str, performance: Dict):
        """更新策略基线"""
        self.strategy_baselines[strategy_id] = performance.copy()

    def record_trade(self, strategy_id: str, trade: Dict):
        """
        记录交易（用于计算最近表现）

        Args:
            strategy_id: 策略ID
            trade: 交易记录
        """
        self.recent_trades[strategy_id].append(trade)

    def calculate_recent_performance(
        self,
        strategy_id: str,
        days: Optional[int] = None
    ) -> Dict:
        """
        计算最近表现

        Args:
            strategy_id: 策略ID
            days: 天数（None表示使用配置的滚动窗口）

        Returns:
            表现指标字典
        """
        if strategy_id not in self.recent_trades:
            return {}

        trades = list(self.recent_trades[strategy_id])

        if not trades:
            return {}

        # 过滤时间范围
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            trades = [t for t in trades if t.get('date', datetime.now()) >= cutoff_date]

        if not trades:
            return {}

        # 计算指标
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 计算最大回撤
        equity_curve = []
        cumulative_pnl = 0
        for trade in trades:
            cumulative_pnl += trade.get('pnl', 0)
            equity_curve.append(cumulative_pnl)

        max_drawdown = 0
        if equity_curve:
            peak = equity_curve[0]
            for value in equity_curve:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)

        return {
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades)
        }

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        strategy_id: Optional[str],
        message: str,
        current_value: float,
        threshold: float,
        metadata: Dict = None
    ) -> Alert:
        """创建告警"""
        alert = Alert(
            timestamp=datetime.now(),
            alert_type=alert_type,
            severity=severity,
            strategy_id=strategy_id,
            message=message,
            current_value=current_value,
            threshold=threshold,
            metadata=metadata or {}
        )
        return alert

    def _handle_alert(self, alert: Alert):
        """处理告警"""
        # 记录告警
        self.alerts.append(alert)
        self.alert_count_by_type[alert.alert_type] += 1
        if alert.strategy_id:
            self.alert_count_by_strategy[alert.strategy_id] += 1

        # 日志
        if alert.severity == 'CRITICAL':
            logger.critical(f"🚨 {alert.message}")
        else:
            logger.warning(f"⚠️  {alert.message}")

        # 执行告警动作
        if alert.severity == 'CRITICAL' and self.config.auto_pause_on_critical:
            if alert.strategy_id:
                self.pause_strategy(alert.strategy_id, reason=alert.message)

        elif alert.severity == 'WARN' and self.config.auto_reduce_position_on_warn:
            logger.warning(f"📉 触发降仓: {alert.strategy_id}")

        # 回调
        if self.alert_callback:
            self.alert_callback(alert)

    def pause_strategy(self, strategy_id: str, reason: str):
        """暂停策略"""
        self.paused_strategies.add(strategy_id)
        logger.critical(f"⛔ 暂停策略 {strategy_id}: {reason}")

    def resume_strategy(self, strategy_id: str):
        """恢复策略"""
        if strategy_id in self.paused_strategies:
            self.paused_strategies.remove(strategy_id)
            logger.info(f"✅ 恢复策略 {strategy_id}")

    def is_strategy_paused(self, strategy_id: str) -> bool:
        """检查策略是否暂停"""
        return strategy_id in self.paused_strategies

    def get_alerts(
        self,
        alert_type: Optional[str] = None,
        strategy_id: Optional[str] = None,
        severity: Optional[str] = None,
        hours: Optional[int] = None
    ) -> List[Alert]:
        """
        查询告警

        Args:
            alert_type: 告警类型过滤
            strategy_id: 策略ID过滤
            severity: 严重程度过滤
            hours: 最近N小时

        Returns:
            告警列表
        """
        filtered = self.alerts

        if alert_type:
            filtered = [a for a in filtered if a.alert_type == alert_type]

        if strategy_id:
            filtered = [a for a in filtered if a.strategy_id == strategy_id]

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            filtered = [a for a in filtered if a.timestamp >= cutoff]

        return filtered

    def get_statistics(self) -> Dict:
        """获取监控统计"""
        return {
            'total_alerts': len(self.alerts),
            'alerts_by_type': dict(self.alert_count_by_type),
            'alerts_by_strategy': dict(self.alert_count_by_strategy),
            'paused_strategies': list(self.paused_strategies),
            'execution_stats': dict(self.execution_stats)
        }

    def reset(self):
        """重置监控器"""
        self.alerts.clear()
        self.alert_count_by_type.clear()
        self.alert_count_by_strategy.clear()
        self.paused_strategies.clear()
        self.recent_trades.clear()
        self.execution_stats.clear()
