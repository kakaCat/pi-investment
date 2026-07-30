#!/usr/bin/env python
"""
V13策略风险检查任务

功能：
- 每天检查累计收益和回撤情况
- 检查是否跑输指数
- 触发条件时发送风险预警到飞书
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from utils.feishu_notifier import create_notifier_from_config
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RiskCheckJob:
    """风险检查任务"""

    def __init__(self, config_path: str):
        """初始化"""
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 初始化仓库
        self.repo = SimulationORMRepository()

        # 初始化飞书通知
        self.feishu_notifier = create_notifier_from_config(self.config)

        # 风险阈值
        self.stop_loss_threshold = self.config['feishu']['observation_period']['stop_loss_threshold']
        self.underperform_threshold = self.config['feishu']['observation_period']['underperform_threshold']

    def _get_index_return_since_start(self) -> float:
        """获取创业板指数从策略开始以来的累计收益率"""
        account = self.repo.get_account(account_name='default')
        if not account:
            return 0.0

        start_date = account.created_at.strftime('%Y-%m-%d')
        current_date = datetime.now().strftime('%Y-%m-%d')

        from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
        kline_repo = KlineRepository()

        # 创业板指数代码
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

        # 获取最新价格
        cursor.execute(
            """
            SELECT close FROM quant.daily_klines
            WHERE symbol = %s AND trade_date <= %s
            ORDER BY trade_date DESC LIMIT 1
            """,
            (index_symbol, current_date)
        )
        end_row = cursor.fetchone()
        cursor.close()

        if not end_row:
            return 0.0

        end_price = end_row[0]

        return (end_price - start_price) / start_price

    def _get_recent_week_return(self) -> float:
        """获取近一周收益率"""
        current_date = datetime.now()
        week_ago = current_date - timedelta(days=7)

        # 获取一周前的账户快照（简化处理，使用当前值估算）
        account = self.repo.get_account(account_name='default')
        if not account:
            return 0.0

        # TODO: 实现更准确的历史账户价值查询
        # 这里简化为返回近期累计收益的一部分
        return account.cumulative_return * 0.3  # 估算值

    def _get_recent_win_rate(self, days: int = 21) -> tuple:
        """
        获取近期胜率和平均收益

        Args:
            days: 统计天数

        Returns:
            (胜率, 平均收益)
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        trades = self.repo.get_trades_since(
            account_name='default',
            since_date=cutoff_date
        )

        if not trades:
            return 0.0, 0.0

        # 按股票分组统计
        stock_returns = {}

        for trade in trades:
            symbol = trade.symbol

            if symbol not in stock_returns:
                stock_returns[symbol] = {'buy_price': 0, 'sell_price': 0, 'shares': 0}

            if trade.direction == 'buy':
                stock_returns[symbol]['buy_price'] = trade.price
                stock_returns[symbol]['shares'] = trade.shares
            elif trade.direction == 'sell':
                stock_returns[symbol]['sell_price'] = trade.price

        # 计算收益
        returns = []
        for symbol, data in stock_returns.items():
            if data['buy_price'] > 0 and data['sell_price'] > 0:
                ret = (data['sell_price'] - data['buy_price']) / data['buy_price']
                returns.append(ret)

        if not returns:
            return 0.0, 0.0

        winning_trades = sum(1 for r in returns if r > 0)
        win_rate = winning_trades / len(returns)
        avg_return = sum(returns) / len(returns)

        return win_rate, avg_return

    def _get_losing_stocks(self) -> list:
        """获取当前主要亏损的股票"""
        positions = self.repo.list_positions(account_name='default')

        losing_stocks = []

        for pos in positions:
            # 获取当前价格
            from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
            kline_repo = KlineRepository()

            cursor = kline_repo.session.connection().connection.cursor()
            cursor.execute(
                """
                SELECT close FROM quant.daily_klines
                WHERE symbol = %s
                ORDER BY trade_date DESC LIMIT 1
                """,
                (pos.symbol,)
            )
            row = cursor.fetchone()
            cursor.close()

            if row:
                current_price = row[0]
                return_rate = (current_price - pos.avg_price) / pos.avg_price

                if return_rate < -0.05:  # 亏损超过5%
                    losing_stocks.append(pos.symbol)

        return losing_stocks

    def run(self):
        """运行风险检查任务"""
        logger.info("开始运行风险检查任务")

        # 获取账户信息
        account = self.repo.get_account(account_name='default')
        if not account:
            logger.warning("账户不存在，跳过风险检查")
            return

        # 账户总资产（多账户重构后由 update_position_prices 实时维护；
        # 旧的 get_account_total_value() 已移除）
        current_value = float(account.total_value or 0)
        # ORM Numeric 字段返回 Decimal，与 float 做算术会 TypeError，统一转 float
        cumulative_return = float(account.cumulative_return or 0)

        logger.info(f"当前累计收益: {cumulative_return*100:.2f}%")

        # 检查是否触发止损
        triggered = False
        trigger_reason = None

        # 条件1: 累计收益 < 止损阈值
        if cumulative_return < self.stop_loss_threshold:
            triggered = True
            trigger_reason = f"累计收益跌破{self.stop_loss_threshold*100:.0f}%"
            logger.warning(f"触发风险预警: {trigger_reason}")

        # 条件2: 跑输指数超过阈值
        index_return = self._get_index_return_since_start()
        underperform = cumulative_return - index_return

        if underperform < -self.underperform_threshold:
            triggered = True
            trigger_reason = f"跑输指数超过{self.underperform_threshold*100:.0f}%"
            logger.warning(f"触发风险预警: {trigger_reason}")

        if not triggered:
            logger.info("未触发风险预警条件")
            return

        # 获取更多统计数据
        weekly_return = self._get_recent_week_return()
        win_rate, avg_return = self._get_recent_win_rate()
        losing_stocks = self._get_losing_stocks()

        # 发送飞书通知
        if self.feishu_notifier:
            notification_data = {
                'trigger': trigger_reason,
                'total_value': current_value,
                'cumulative_return': cumulative_return,
                'weekly_return': weekly_return,
                'index_return': index_return,
                'win_rate': win_rate,
                'avg_return': avg_return,
                'losing_stocks': losing_stocks
            }

            success = self.feishu_notifier.send_risk_alert(notification_data)

            if success:
                logger.info("风险预警通知发送成功")
            else:
                logger.error("风险预警通知发送失败")

        logger.info("风险检查任务完成")


def main():
    """主函数"""
    # 使用绝对路径
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / 'live_trading' / 'config_simulation.yaml'

    job = RiskCheckJob(config_path=str(config_path))
    job.run()


# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数"""
    main()


if __name__ == '__main__':
    main()
