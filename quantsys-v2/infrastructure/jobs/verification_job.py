#!/usr/bin/env python
"""
V13策略预测验证任务

功能：
- 每天检查是否有5个交易日前的调仓记录
- 计算预测收益 vs 实际收益
- 发送验证通知到飞书
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


class VerificationJob:
    """预测验证任务"""

    def __init__(self, config_path: str):
        """初始化"""
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 初始化仓库
        self.repo = SimulationORMRepository()

        # 初始化飞书通知
        self.feishu_notifier = create_notifier_from_config(self.config)

    def _is_trading_day(self, date_str: str) -> bool:
        """检查是否为交易日"""
        date = datetime.strptime(date_str, '%Y-%m-%d')

        # 排除周末
        if date.weekday() >= 5:
            return False

        # 检查数据库中是否有K线数据
        from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
        kline_repo = KlineRepository()

        # 简单检查：如果任意股票在该日期有K线数据，则认为是交易日
        cursor = kline_repo.session.connection().connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date = %s LIMIT 1",
            (date_str,)
        )
        count = cursor.fetchone()[0]
        cursor.close()

        return count > 0

    def _count_trading_days_between(self, start_date: str, end_date: str) -> int:
        """计算两个日期之间的交易日数量"""
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        count = 0
        current = start + timedelta(days=1)  # 不包含起始日

        while current <= end:
            if self._is_trading_day(current.strftime('%Y-%m-%d')):
                count += 1
            current += timedelta(days=1)

        return count

    def _get_stock_return(self, symbol: str, start_date: str, end_date: str) -> float:
        """
        获取股票在指定期间的收益率

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            收益率（小数形式）
        """
        from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
        kline_repo = KlineRepository()

        # 获取起始价格
        cursor = kline_repo.session.connection().connection.cursor()
        cursor.execute(
            """
            SELECT close FROM quant.daily_klines
            WHERE symbol = %s AND trade_date >= %s
            ORDER BY trade_date ASC LIMIT 1
            """,
            (symbol, start_date)
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
            (symbol, end_date)
        )
        end_row = cursor.fetchone()
        cursor.close()

        if not end_row:
            return 0.0

        end_price = end_row[0]

        # 计算收益率
        return (end_price - start_price) / start_price

    def _get_index_return(self, start_date: str, end_date: str) -> float:
        """
        获取创业板指数在指定期间的收益率

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            收益率（小数形式）
        """
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

    def run(self):
        """运行验证任务"""
        logger.info("开始运行预测验证任务")

        current_date = datetime.now().strftime('%Y-%m-%d')

        # 检查今天是否为交易日
        if not self._is_trading_day(current_date):
            logger.info(f"{current_date} 不是交易日，跳过验证")
            return

        # 获取所有调仓记录
        account = self.repo.get_account(account_name='default')
        if not account or not account.last_rebalance_date:
            logger.info("没有调仓记录，跳过验证")
            return

        last_rebalance_date = account.last_rebalance_date

        # 计算距离上次调仓的交易日数
        trading_days = self._count_trading_days_between(last_rebalance_date, current_date)

        logger.info(f"上次调仓日期: {last_rebalance_date}, 距今{trading_days}个交易日")

        # 只在第5个交易日后验证
        if trading_days != 5:
            logger.info(f"当前是第{trading_days}个交易日，等待第5个交易日")
            return

        logger.info("到达验证时间点，开始验证预测准确性")

        # 获取调仓时的持仓
        trades = self.repo.get_trades_by_date(
            account_name='default',
            trade_date=last_rebalance_date
        )

        # 筛选出买入交易（即本次调仓选中的股票）
        buy_trades = [t for t in trades if t.direction == 'buy']

        if not buy_trades:
            logger.info("没有买入交易记录，跳过验证")
            return

        # 计算每只股票的预测收益 vs 实际收益
        predictions = []

        for trade in buy_trades:
            symbol = trade.symbol

            # 获取实际收益
            actual_return = self._get_stock_return(
                symbol,
                last_rebalance_date,
                current_date
            )

            # 预测收益从备注中提取（如果有保存）
            # 这里简化处理，假设预测收益率在10-15%之间
            # 实际应该从调仓时保存的预测数据中读取
            predicted_return = 0.12  # TODO: 从实际数据读取

            predictions.append((symbol, predicted_return, actual_return))

            logger.info(
                f"{symbol}: 预测{predicted_return*100:+.2f}%, "
                f"实际{actual_return*100:+.2f}%"
            )

        # 获取账户变化（多账户重构后 total_value 由 update_position_prices 维护；
        # 旧的 get_account_total_value() 已移除）
        # ORM Numeric 字段返回 Decimal，统一转 float 避免算术/JSON 序列化问题
        initial_value = float(account.initial_capital or 0) * (1 + float(account.cumulative_return or 0))
        current_value = float(account.total_value or 0)
        period_return = (current_value - initial_value) / initial_value

        # 获取指数收益
        index_return = self._get_index_return(last_rebalance_date, current_date)

        # 计算当前是第几个周期
        rebalance_days = self.config['strategy']['rebalance_days']
        total_rebalances = self.repo.count_rebalances(account_name='default')
        cycle = total_rebalances

        # 发送飞书通知
        if self.feishu_notifier:
            notification_data = {
                'rebalance_date': last_rebalance_date,
                'verify_date': current_date,
                'predictions': predictions,
                'initial_value': initial_value,
                'current_value': current_value,
                'period_return': period_return,
                'index_return': index_return,
                'cycle': cycle
            }

            success = self.feishu_notifier.send_verification_notification(notification_data)

            if success:
                logger.info("验证通知发送成功")
            else:
                logger.error("验证通知发送失败")

        logger.info("预测验证任务完成")


def main():
    """主函数"""
    # 使用绝对路径
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / 'live_trading' / 'config_simulation.yaml'

    job = VerificationJob(config_path=str(config_path))
    job.run()


# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数"""
    main()


if __name__ == '__main__':
    main()
