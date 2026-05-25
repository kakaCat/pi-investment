"""
策略漂移检测器 - Strategy Drift Detector

检测策略表现是否偏离历史基线，及时发现策略失效。

检测指标:
1. 胜率变化
2. 盈亏比变化
3. 最大回撤变化
4. 夏普比率变化
5. 卡玛比率变化

使用示例:
    detector = DriftDetector(rolling_days=20)

    # 更新交易记录
    detector.record_trade(strategy_id, trade)

    # 检测漂移
    has_drift, metrics = detector.detect_drift(strategy_id)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
import math


@dataclass
class DriftMetrics:
    """漂移指标"""
    strategy_id: str
    baseline: Dict
    current: Dict
    changes: Dict
    has_drift: bool
    drift_reasons: List[str]


class DriftDetector:
    """
    策略漂移检测器

    对比最近表现与历史基线，检测策略是否失效。
    """

    def __init__(
        self,
        rolling_days: int = 20,
        baseline_days: int = 60,
        win_rate_threshold: float = 0.08,
        pl_ratio_threshold: float = 0.2,
        drawdown_threshold: float = 0.3,
        sharpe_threshold: float = 0.3
    ):
        """
        初始化漂移检测器

        Args:
            rolling_days: 滚动窗口天数（计算最近表现）
            baseline_days: 基线天数（计算历史基线）
            win_rate_threshold: 胜率下降阈值
            pl_ratio_threshold: 盈亏比下降阈值
            drawdown_threshold: 回撤扩大阈值
            sharpe_threshold: 夏普比率下降阈值
        """
        self.rolling_days = rolling_days
        self.baseline_days = baseline_days
        self.win_rate_threshold = win_rate_threshold
        self.pl_ratio_threshold = pl_ratio_threshold
        self.drawdown_threshold = drawdown_threshold
        self.sharpe_threshold = sharpe_threshold

        # 交易记录
        self.trades: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

        # 基线缓存
        self.baselines: Dict[str, Dict] = {}

    def record_trade(self, strategy_id: str, trade: Dict):
        """
        记录交易

        Args:
            strategy_id: 策略ID
            trade: 交易记录，需包含:
                - date: 日期
                - pnl: 盈亏
                - return_pct: 收益率
        """
        self.trades[strategy_id].append(trade)

    def detect_drift(
        self,
        strategy_id: str,
        update_baseline: bool = False
    ) -> Tuple[bool, DriftMetrics]:
        """
        检测策略漂移

        Args:
            strategy_id: 策略ID
            update_baseline: 是否更新基线

        Returns:
            (has_drift, drift_metrics)
        """
        if strategy_id not in self.trades:
            return False, None

        # 计算基线（如果没有缓存）
        if strategy_id not in self.baselines or update_baseline:
            baseline = self._calculate_baseline(strategy_id)
            if not baseline:
                return False, None
            self.baselines[strategy_id] = baseline
        else:
            baseline = self.baselines[strategy_id]

        # 计算最近表现
        current = self._calculate_recent_performance(strategy_id)
        if not current:
            return False, None

        # 对比指标
        changes = {}
        drift_reasons = []
        has_drift = False

        # 1. 胜率变化
        if 'win_rate' in baseline and 'win_rate' in current:
            win_rate_change = baseline['win_rate'] - current['win_rate']
            changes['win_rate'] = win_rate_change

            if win_rate_change >= self.win_rate_threshold:
                has_drift = True
                drift_reasons.append(
                    f"胜率下降 {win_rate_change:.2%} "
                    f"(基线: {baseline['win_rate']:.2%}, "
                    f"当前: {current['win_rate']:.2%})"
                )

        # 2. 盈亏比变化
        if 'profit_loss_ratio' in baseline and 'profit_loss_ratio' in current:
            if baseline['profit_loss_ratio'] > 0:
                pl_ratio_change = (baseline['profit_loss_ratio'] - current['profit_loss_ratio']) / baseline['profit_loss_ratio']
                changes['profit_loss_ratio'] = pl_ratio_change

                if pl_ratio_change >= self.pl_ratio_threshold:
                    has_drift = True
                    drift_reasons.append(
                        f"盈亏比下降 {pl_ratio_change:.2%} "
                        f"(基线: {baseline['profit_loss_ratio']:.2f}, "
                        f"当前: {current['profit_loss_ratio']:.2f})"
                    )

        # 3. 最大回撤变化
        if 'max_drawdown' in baseline and 'max_drawdown' in current:
            if baseline['max_drawdown'] > 0:
                dd_change = (current['max_drawdown'] - baseline['max_drawdown']) / baseline['max_drawdown']
                changes['max_drawdown'] = dd_change

                if dd_change >= self.drawdown_threshold:
                    has_drift = True
                    drift_reasons.append(
                        f"最大回撤扩大 {dd_change:.2%} "
                        f"(基线: {baseline['max_drawdown']:.2%}, "
                        f"当前: {current['max_drawdown']:.2%})"
                    )

        # 4. 夏普比率变化
        if 'sharpe_ratio' in baseline and 'sharpe_ratio' in current:
            if baseline['sharpe_ratio'] > 0:
                sharpe_change = (baseline['sharpe_ratio'] - current['sharpe_ratio']) / baseline['sharpe_ratio']
                changes['sharpe_ratio'] = sharpe_change

                if sharpe_change >= self.sharpe_threshold:
                    has_drift = True
                    drift_reasons.append(
                        f"夏普比率下降 {sharpe_change:.2%} "
                        f"(基线: {baseline['sharpe_ratio']:.2f}, "
                        f"当前: {current['sharpe_ratio']:.2f})"
                    )

        metrics = DriftMetrics(
            strategy_id=strategy_id,
            baseline=baseline,
            current=current,
            changes=changes,
            has_drift=has_drift,
            drift_reasons=drift_reasons
        )

        return has_drift, metrics

    def _calculate_baseline(self, strategy_id: str) -> Optional[Dict]:
        """计算历史基线"""
        trades = list(self.trades[strategy_id])

        if not trades:
            return None

        # 使用较早的数据作为基线
        cutoff_date = datetime.now() - timedelta(days=self.baseline_days)
        baseline_trades = [t for t in trades if t.get('date', datetime.now()) < cutoff_date]

        if not baseline_trades:
            # 如果没有足够的历史数据，使用全部数据
            baseline_trades = trades[:len(trades)//2] if len(trades) > 10 else trades

        return self._calculate_metrics(baseline_trades)

    def _calculate_recent_performance(self, strategy_id: str) -> Optional[Dict]:
        """计算最近表现"""
        trades = list(self.trades[strategy_id])

        if not trades:
            return None

        # 使用最近的数据
        cutoff_date = datetime.now() - timedelta(days=self.rolling_days)
        recent_trades = [t for t in trades if t.get('date', datetime.now()) >= cutoff_date]

        if not recent_trades:
            recent_trades = trades[-min(20, len(trades)):]  # 至少取最近20笔

        return self._calculate_metrics(recent_trades)

    def _calculate_metrics(self, trades: List[Dict]) -> Dict:
        """计算性能指标"""
        if not trades:
            return {}

        # 基础指标
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 最大回撤
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

        # 夏普比率
        returns = [t.get('return_pct', 0) for t in trades if 'return_pct' in t]
        sharpe_ratio = 0
        if returns and len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            std_return = math.sqrt(sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1))
            sharpe_ratio = (mean_return / std_return * math.sqrt(252)) if std_return > 0 else 0

        # 卡玛比率
        calmar_ratio = 0
        if max_drawdown > 0:
            total_return = sum(t.get('pnl', 0) for t in trades)
            calmar_ratio = total_return / max_drawdown if max_drawdown > 0 else 0

        return {
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'calmar_ratio': calmar_ratio,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }

    def get_all_drifts(self) -> Dict[str, DriftMetrics]:
        """获取所有策略的漂移情况"""
        results = {}

        for strategy_id in self.trades.keys():
            has_drift, metrics = self.detect_drift(strategy_id)
            if metrics:
                results[strategy_id] = metrics

        return results

    def reset_baseline(self, strategy_id: str):
        """重置策略基线"""
        if strategy_id in self.baselines:
            del self.baselines[strategy_id]
