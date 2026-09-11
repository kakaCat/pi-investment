#!/usr/bin/env python
"""
V13策略周报任务

功能：
- 每周一生成上周的交易周报
- 统计收益、胜率、交易次数等
- 发送周报到飞书
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent.parent

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from application.notification.notification_factory import get_notification_facade
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyReportJob:
    """周报任务"""

    ACCOUNT_NAME = 'v13_simulation'  # V13 策略账户（此前误用已冻结的 default）

    def __init__(self, config_path: str):
        """初始化"""
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 初始化仓库
        self.repo = SimulationORMRepository()

        # 初始化通知门面（使用新的 DDD 通知系统）
        self.notification_facade = get_notification_facade()

    def _get_week_range(self) -> tuple:
        """
        获取上周的日期范围（周一到周五）

        Returns:
            (start_date, end_date)
        """
        today = datetime.now()

        # 获取上周一
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)

        # 获取上周五
        last_friday = last_monday + timedelta(days=4)

        return (
            last_monday.strftime('%Y-%m-%d'),
            last_friday.strftime('%Y-%m-%d')
        )

    def _get_account_value_at_date(self, date_str: str) -> float:
        """获取指定日期（含）之前最近一条净值快照的账户总资产，始终返回 float。

        2026-09-11 修复（w-f4aa1f6a，看板事件 271）：
        - 原实现是 TODO 桩，直接返回 account.initial_capital（且是 ORM 的 Decimal）：
          ① 语义错误——"本周收益"实为"累计收益"（数字对外发布是错的）；
          ② 类型错误——与 float 的 final_value 混算抛
          TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'，
          任务每天/每周失败（事件 1d87e242 / c4e93003 / 271 同源）。
        - 现按 snapshot_date <= date_str 取最近一条快照的 total_value；
          无快照（或日期不可解析）时回退 initial_capital，并 WARNING 留痕。
        """
        try:
            target = datetime.fromisoformat(str(date_str)).date()
        except (TypeError, ValueError):
            logger.warning(f"日期无法解析，回退初始资金: {date_str!r}")
            target = None

        snapshots = []
        if target is not None:
            try:
                snapshots = self.repo.get_equity_snapshots(self.ACCOUNT_NAME, limit=400) or []
            except Exception as e:
                logger.warning(f"读取净值快照失败，回退初始资金: {e}")

        for snap in snapshots:  # 已按 snapshot_date 倒序，第一条满足 <= target 即最近
            snap_date = getattr(snap, 'snapshot_date', None)
            if snap_date is not None and snap_date <= target:
                value = getattr(snap, 'total_value', None)
                if value is not None:
                    return float(value)

        account = self.repo.get_account(account_name=self.ACCOUNT_NAME)
        base = getattr(account, 'initial_capital', None) if account else None
        logger.warning(f"{date_str} 无可用净值快照，回退初始资金: {base}")
        return float(base) if base is not None else 100000.0

    def _calculate_position_returns(self, start_date: str, end_date: str) -> list:
        """
        计算期间内各持仓股票的收益率

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            收益率列表
        """
        positions = self.repo.get_all_positions(account_name=self.ACCOUNT_NAME)
        returns = []

        from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
        kline_repo = KlineRepository()

        for pos in positions:
            cursor = kline_repo.session.connection().connection.cursor()

            # 获取期初价格
            cursor.execute(
                """
                SELECT close FROM quant.daily_klines
                WHERE symbol = %s AND trade_date >= %s
                ORDER BY trade_date ASC LIMIT 1
                """,
                (pos.symbol, start_date)
            )
            start_row = cursor.fetchone()

            if not start_row:
                cursor.close()
                continue

            start_price = start_row[0]

            # 获取期末价格
            cursor.execute(
                """
                SELECT close FROM quant.daily_klines
                WHERE symbol = %s AND trade_date <= %s
                ORDER BY trade_date DESC LIMIT 1
                """,
                (pos.symbol, end_date)
            )
            end_row = cursor.fetchone()
            cursor.close()

            if not end_row:
                continue

            end_price = end_row[0]

            ret = (end_price - start_price) / start_price
            returns.append(ret)

        return returns

    def _get_index_return(self, start_date: str, end_date: str) -> float:
        """获取创业板指数收益率"""
        from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
        kline_repo = KlineRepository()

        index_symbol = '399006'

        cursor = kline_repo.session.connection().connection.cursor()

        # 获取起始价格
        cursor.execute(
            """
            SELECT close FROM quant.daily_klines
            WHERE symbol = %s AND trade_date >= %s
            ORDER BY trade_date ASC LIMIT 1
            """,
            (index_symbol, start_date)
        )
        start_row = cursor.fetchone()

        if not start_row:
            cursor.close()
            return 0.0

        start_price = start_row[0]

        # 获取结束价格
        cursor.execute(
            """
            SELECT close FROM quant.daily_klines
            WHERE symbol = %s AND trade_date <= %s
            ORDER BY trade_date DESC LIMIT 1
            """,
            (index_symbol, end_date)
        )
        end_row = cursor.fetchone()
        cursor.close()

        if not end_row:
            return 0.0

        end_price = end_row[0]

        return (end_price - start_price) / start_price

    def _get_next_rebalance_date(self) -> str:
        """获取下次调仓日期"""
        account = self.repo.get_account(account_name=self.ACCOUNT_NAME)
        if not account or not account.last_rebalance_date:
            return "未知"

        last_rebalance = datetime.strptime(str(account.last_rebalance_date), '%Y-%m-%d')
        rebalance_days = self.config['strategy']['rebalance_days']

        # 简化计算，实际应该按交易日计算
        next_rebalance = last_rebalance + timedelta(days=rebalance_days + 2)

        return next_rebalance.strftime('%Y-%m-%d')

    def run(self):
        """运行周报任务"""
        logger.info("开始生成V13策略周报")

        # 获取上周日期范围
        start_date, end_date = self._get_week_range()
        logger.info(f"统计周期: {start_date} ~ {end_date}")

        # 获取账户信息
        account = self.repo.get_account(account_name=self.ACCOUNT_NAME)
        if not account:
            logger.warning("账户不存在，跳过周报生成")
            # 2026-09-11（w-f4aa1f6a）：不再静默 return None——账户缺失是配置错误，
            # 必须让调度层看到 failed（原实现返回 None 被包装成假成功）
            return {
                'status': 'failed',
                'error': f'账户不存在: {self.ACCOUNT_NAME}',
                'account_name': self.ACCOUNT_NAME,
            }

        # 计算周初和周末账户价值
        initial_value = self._get_account_value_at_date(start_date)
        final_value = float(account.total_value)

        # 计算本周收益
        weekly_return = (final_value - initial_value) / initial_value if initial_value else 0.0

        # 获取本周交易数据
        trades = self.repo.get_trades_by_account(
            account_name=self.ACCOUNT_NAME,
            start_date=start_date,
            end_date=end_date
        )

        # 统计调仓次数（买入交易日期去重）
        rebalance_dates = set()
        for trade in trades:
            if trade.action == 'BUY':
                rebalance_dates.add(trade.trade_date)

        rebalance_count = len(rebalance_dates)

        # 统计交易股票数
        traded_symbols = set(trade.symbol for trade in trades)
        total_stocks = len(traded_symbols)

        # 计算持仓收益率
        position_returns = self._calculate_position_returns(start_date, end_date)

        win_count = sum(1 for r in position_returns if r > 0)
        avg_position_return = sum(position_returns) / len(position_returns) if position_returns else 0

        # 计算最大回撤（简化）
        max_drawdown = min(position_returns) if position_returns else 0

        # 获取当前仓位水平
        positions = self.repo.get_all_positions(account_name=self.ACCOUNT_NAME)
        cash = float(account.cash_available)
        position_level = (final_value - cash) / final_value if final_value > 0 else 0

        # 止损次数（简化，从交易记录中统计卖出且亏损的）
        stop_loss_count = 0
        # TODO: 更准确的止损统计

        # 获取指数收益
        index_return = self._get_index_return(start_date, end_date)
        excess_return = weekly_return - index_return

        # 下次调仓日期
        next_rebalance_date = self._get_next_rebalance_date()

        # 观察期进度
        all_trades = self.repo.get_trades_by_account(account_name=self.ACCOUNT_NAME)
        total_rebalances = len({t.trade_date for t in all_trades if t.action == 'BUY'})
        observation_cycles = self.config['feishu']['observation_period']['cycles']
        observation_progress = f"{total_rebalances}/{observation_cycles}"

        # 计算第几周
        account_start_date = account.created_at
        weeks_elapsed = (datetime.now() - account_start_date).days // 7 + 1

        # 发送周报通知
        notification_data = {
            'week': weeks_elapsed,
            'start_date': start_date,
            'end_date': end_date,
            'initial_value': initial_value,
            'final_value': final_value,
            'weekly_return': weekly_return,
            'rebalance_count': rebalance_count,
            'trade_count': len(trades),
            'win_count': win_count,
            'total_stocks': total_stocks,
            'avg_position_return': avg_position_return,
            'max_drawdown': max_drawdown,
            'position_level': position_level,
            'stop_loss_count': stop_loss_count,
            'index_return': index_return,
            'excess_return': excess_return,
            'next_rebalance_date': next_rebalance_date,
            'observation_progress': observation_progress
        }

        # 2026-09-11（w-f4aa1f6a）：通知结果必须回传，不再"发送失败仍报完成"
        send_ok = False
        send_error = None
        try:
            result = self.notification_facade.send_weekly_report(notification_data)

            if result.success:
                logger.info("周报发送成功")
                send_ok = True
            else:
                send_error = getattr(result, 'error', None) or '通知渠道返回 success=False'
                logger.error(f"周报发送失败: {send_error}")
        except Exception as e:
            send_error = str(e)
            logger.error(f"发送周报异常: {e}")

        logger.info("周报生成完成")
        return {
            'status': 'completed' if send_ok else 'failed',
            'strategy': 'v13',
            'account_name': self.ACCOUNT_NAME,
            'start_date': start_date,
            'end_date': end_date,
            'initial_value': initial_value,
            'final_value': final_value,
            'weekly_return_pct': round(weekly_return * 100, 4),
            'trade_count': len(trades),
            'rebalance_count': rebalance_count,
            'notification_sent': send_ok,
            'error': send_error,
        }


def main():
    """主函数"""
    # 使用绝对路径
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / 'live_trading' / 'config_simulation.yaml'

    job = WeeklyReportJob(config_path=str(config_path))
    return job.run()


# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数（返回结构化结果供调度层判定成败）"""
    return main()


if __name__ == '__main__':
    main()
