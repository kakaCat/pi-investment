"""
全局绩效追踪服务 (Performance Tracker)

提供统一的投资绩效查询 API，回答：
- 系统上线以来总共赚了多少？
- 哪个策略贡献最大？
- 最近一个月最大回撤是多少？
- 当前持仓的总成本、市值、浮盈是多少？

数据来源：
- simulation_equity_snapshot（每日净值）
- simulation_trade（交易记录）
- simulation_positions（当前持仓）
- simulation_account（账户汇总）
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta

from domain.ports import ISimulationRepository

logger = structlog.get_logger(__name__)


class PerformanceTracker:
    """全局绩效追踪器

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        account_name: str = 'rotation_main',
        repo: Optional[ISimulationRepository] = None,
    ):
        """初始化服务

        Args:
            account_name: 账户名称
            repo: 模拟仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.account_name = account_name
        self.repo = repo

    def get_full_report(self) -> Dict[str, Any]:
        """生成完整绩效报告"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': f'Account {self.account_name} not found'}

        return {
            'account': self._account_summary(account),
            'positions': self._position_summary(),
            'performance': self._performance_metrics(),
            'strategy_attribution': self._strategy_attribution(),
            'recent_trades': self._recent_trades(limit=20),
        }

    def get_quick_stats(self) -> Dict[str, Any]:
        """快速获取关键指标"""
        account = self.repo.get_account(self.account_name)
        if account is None:
            return {'error': 'Account not found'}

        initial = float(account.initial_capital or 0)
        total_value = float(account.total_value or 0)
        cumulative_return = (total_value - initial) / initial if initial > 0 else 0

        return {
            'account_name': self.account_name,
            'date': date.today().isoformat(),
            'initial_capital': initial,
            'total_value': round(total_value, 2),
            'cash_available': float(account.cash_available or 0),
            'position_value': float(account.position_value or 0),
            'cumulative_return': round(cumulative_return, 4),
            'cumulative_return_pct': f"{cumulative_return:.2%}",
            'max_drawdown': float(account.max_drawdown or 0),
            'max_drawdown_pct': f"{float(account.max_drawdown or 0):.2%}",
        }

    # ==================== 内部方法 ====================

    def _account_summary(self, account) -> Dict[str, Any]:
        """账户摘要"""
        initial = float(account.initial_capital or 0)
        total_value = float(account.total_value or 0)
        cumulative_return = (total_value - initial) / initial if initial > 0 else 0

        # 计算运行天数
        created = account.created_at
        running_days = (datetime.now() - created).days if created else 0

        # 年化收益率
        annual_return = 0
        if running_days > 0:
            annual_return = (1 + cumulative_return) ** (365 / running_days) - 1

        return {
            'account_name': account.account_name,
            'display_name': account.display_name,
            'status': account.status,
            'initial_capital': initial,
            'total_value': round(total_value, 2),
            'cash_available': float(account.cash_available or 0),
            'cash_frozen': float(account.cash_frozen or 0),
            'position_value': float(account.position_value or 0),
            'cumulative_return': round(cumulative_return, 4),
            'annual_return': round(annual_return, 4),
            'max_drawdown': float(account.max_drawdown or 0),
            'peak_value': float(account.peak_value or 0),
            'running_days': running_days,
            'created_at': created.isoformat() if created else None,
        }

    def _position_summary(self) -> Dict[str, Any]:
        """持仓汇总"""
        positions = self.repo.get_all_positions(self.account_name, only_nonzero=True)

        total_cost = sum(float(p.cost or 0) for p in positions)
        total_market_value = sum(float(p.market_value or 0) for p in positions)
        total_profit = sum(float(p.profit_total or 0) for p in positions)

        position_details = []
        for p in positions:
            position_details.append({
                'symbol': p.symbol,
                'shares': p.shares_total,
                'avg_cost': float(p.avg_cost or 0),
                'current_price': float(p.current_price or 0),
                'market_value': float(p.market_value or 0),
                'cost': float(p.cost or 0),
                'profit': float(p.profit_total or 0),
                'profit_rate': float(p.profit_total_rate or 0),
            })

        return {
            'count': len(positions),
            'total_cost': round(total_cost, 2),
            'total_market_value': round(total_market_value, 2),
            'total_profit': round(total_profit, 2),
            'profit_rate': round(total_profit / total_cost, 4) if total_cost > 0 else 0,
            'positions': position_details,
        }

    def _performance_metrics(self) -> Dict[str, Any]:
        """绩效指标（基于净值快照）"""
        snapshots = self.repo.get_equity_snapshots(self.account_name, limit=90)

        if not snapshots:
            return {'message': 'No snapshots yet'}

        # 最近30天收益率
        recent_30d = snapshots[:30] if len(snapshots) >= 30 else snapshots
        if len(recent_30d) >= 2:
            start_value = float(recent_30d[-1].total_value or 0)
            end_value = float(recent_30d[0].total_value or 0)
            return_30d = (end_value - start_value) / start_value if start_value > 0 else 0
        else:
            return_30d = 0

        # 最大回撤（从快照计算）
        max_drawdown = self._calculate_max_drawdown(snapshots)

        # 日收益率序列
        daily_returns = [float(s.daily_return or 0) for s in snapshots if s.daily_return]

        # 胜率（日收益率 > 0 的比例）
        win_days = sum(1 for r in daily_returns if r > 0)
        win_rate = win_days / len(daily_returns) if daily_returns else 0

        # 夏普比率（简化版）
        if daily_returns:
            import statistics
            avg_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 1
            sharpe = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        else:
            sharpe = 0

        return {
            'return_30d': round(return_30d, 4),
            'return_30d_pct': f"{return_30d:.2%}",
            'max_drawdown': round(max_drawdown, 4),
            'max_drawdown_pct': f"{max_drawdown:.2%}",
            'sharpe_ratio': round(sharpe, 2),
            'win_rate_daily': round(win_rate, 4),
            'trading_days': len(snapshots),
            'avg_daily_return': round(statistics.mean(daily_returns), 6) if daily_returns else 0,
        }

    def _calculate_max_drawdown(self, snapshots) -> float:
        """从净值序列计算最大回撤"""
        if not snapshots:
            return 0

        # snapshots 是按日期倒序的，需要反转
        values = [float(s.total_value or 0) for s in reversed(snapshots)]

        peak = values[0] if values else 0
        max_dd = 0

        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

        return max_dd

    def _strategy_attribution(self) -> List[Dict[str, Any]]:
        """策略归因（按策略统计盈亏贡献）"""
        try:
            trades = self.repo.get_trades_by_account(self.account_name)

            # 按策略分组统计
            strategy_stats: Dict[str, Dict] = {}

            for trade in trades:
                reason = trade.reason or 'unknown'
                # 从 reason 中提取策略名（格式: "strategy_name: detail"）
                strategy_name = reason.split(':')[0].strip() if ':' in reason else reason

                if strategy_name not in strategy_stats:
                    strategy_stats[strategy_name] = {
                        'strategy_name': strategy_name,
                        'total_trades': 0,
                        'buy_count': 0,
                        'sell_count': 0,
                        'total_pnl': 0,
                        'total_commission': 0,
                    }

                stats = strategy_stats[strategy_name]
                stats['total_trades'] += 1

                if trade.action == 'BUY':  # action 大写契约（08-13 统一）
                    stats['buy_count'] += 1
                else:
                    stats['sell_count'] += 1
                    stats['total_pnl'] += float(trade.realized_pnl or 0)

                stats['total_commission'] += float(trade.commission or 0) + float(trade.stamp_duty or 0)

            # 按盈亏排序
            result = sorted(
                strategy_stats.values(),
                key=lambda x: x['total_pnl'],
                reverse=True
            )

            return result

        except Exception as e:
            logger.error(f"Strategy attribution failed: {e}")
            return []

    def _recent_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """最近交易记录"""
        trades = self.repo.get_trades(self.account_name, limit=limit)
        return [t.to_dict() for t in trades]


# ============================================================
# 全局单例
# ============================================================

_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker(account_name: str = 'rotation_main') -> PerformanceTracker:
    """获取绩效追踪器"""
    global _tracker
    if _tracker is None or _tracker.account_name != account_name:
        _tracker = PerformanceTracker(account_name)
    return _tracker
