#!/usr/bin/env python
"""
策略风险检查任务（通用版，支持所有策略账户）

功能：
1. 每日检查单股止损（-15% 默认阈值）
2. 检查组合级风险（累计收益、跑输指数）
3. 自动执行止损（可选）或发送告警通知

设计：
- 配置驱动：从策略配置文件读取账户名和止损阈值
- 支持所有策略：v13/v14/v15...
- 独立于调仓周期：每天运行，不受调仓周期限制

使用方式：
    # 检查单个策略
    strategy_risk_check('v13')

    # 检查所有启用策略
    strategy_risk_check_all()
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from adapters.outbound.repositories.kline_repository import KlineORMRepository as KlineRepository
from application.notification.notification_factory import get_notification_facade
from application.services.strategy_service import StrategyService
from live_trading.simulation_trader import SimulationTrader
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StrategyRiskChecker:
    """策略风险检查器（通用版）"""

    def __init__(self, strategy_name: str, auto_execute_stop_loss: bool = False):
        """初始化

        Args:
            strategy_name: 策略名称（如 'v13', 'v14'）
            auto_execute_stop_loss: 是否自动执行止损（False=仅告警）
        """
        self.strategy_name = strategy_name
        self.auto_execute = auto_execute_stop_loss

        # 加载策略配置
        strategy_service = StrategyService()
        self.config = strategy_service.get_config(strategy_name)
        self.account_name = self.config['strategy']['account_name']

        # 初始化仓库
        self.repo = SimulationORMRepository()
        self.kline_repo = KlineRepository()

        # 初始化通知门面
        self.notification_facade = get_notification_facade()

        # 风险阈值（从配置读取）
        self.single_stop_loss = self.config.get('risk', {}).get('single_stock_stop_loss', -0.15)
        self.portfolio_stop_loss = self.config.get('risk', {}).get('portfolio_stop_loss', -0.20)

        logger.info(f"风险检查器初始化: {strategy_name}")
        logger.info(f"  账户: {self.account_name}")
        logger.info(f"  单股止损: {self.single_stop_loss:.0%}")
        logger.info(f"  组合止损: {self.portfolio_stop_loss:.0%}")
        logger.info(f"  自动止损: {'是' if self.auto_execute else '否（仅告警）'}")

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """获取股票当前价格"""
        try:
            cursor = self.kline_repo.session.connection().connection.cursor()
            cursor.execute(
                """
                SELECT close FROM quant.daily_klines
                WHERE symbol = %s
                ORDER BY trade_date DESC LIMIT 1
                """,
                (symbol,)
            )
            row = cursor.fetchone()
            cursor.close()

            if row:
                return float(row[0])
        except Exception as e:
            logger.error(f"获取 {symbol} 价格失败: {e}")

        return None

    def check_single_stock_stop_loss(self) -> List[Dict]:
        """检查单股止损

        Returns:
            List[Dict]: 触发止损的股票列表
                - symbol: 股票代码
                - name: 股票名称
                - avg_cost: 成本价
                - current_price: 当前价
                - pnl_pct: 浮亏比例
                - position_value: 持仓市值
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"检查单股止损: {self.strategy_name} ({self.account_name})")
        logger.info(f"{'='*60}")

        positions = self.repo.get_all_positions(self.account_name)

        if not positions:
            logger.info("无持仓，跳过检查")
            return []

        logger.info(f"持仓数量: {len(positions)}只")

        stop_loss_list = []

        for pos in positions:
            symbol = pos.symbol
            avg_cost = float(pos.avg_cost)
            shares = int(pos.shares_total)

            # 获取当前价格
            current_price = self._get_current_price(symbol)
            if not current_price:
                logger.warning(f"{symbol}: 无法获取当前价格，跳过")
                continue

            # 计算浮亏比例
            pnl_pct = (current_price - avg_cost) / avg_cost
            position_value = shares * current_price

            logger.info(f"{symbol}: 成本¥{avg_cost:.2f}, 现价¥{current_price:.2f}, "
                       f"浮盈亏{pnl_pct:+.2%}, 市值¥{position_value:,.0f}")

            # 检查是否触发止损
            if pnl_pct <= self.single_stop_loss:
                logger.warning(f"🚨 {symbol} 触发止损: {pnl_pct:.2%} <= {self.single_stop_loss:.2%}")

                # 获取股票名称
                try:
                    cursor = self.repo.session.connection().connection.cursor()
                    cursor.execute("SELECT name FROM quant.stocks WHERE symbol = %s", (symbol,))
                    name_row = cursor.fetchone()
                    stock_name = name_row[0] if name_row else symbol
                    cursor.close()
                except:
                    stock_name = symbol

                stop_loss_list.append({
                    'symbol': symbol,
                    'name': stock_name,
                    'avg_cost': avg_cost,
                    'current_price': current_price,
                    'pnl_pct': pnl_pct,
                    'shares': shares,
                    'position_value': position_value,
                    'stop_loss_threshold': self.single_stop_loss
                })

        if stop_loss_list:
            logger.warning(f"\n触发止损: {len(stop_loss_list)}只股票")
        else:
            logger.info(f"\n✅ 无股票触发止损")

        return stop_loss_list

    def check_portfolio_risk(self) -> Dict:
        """检查组合级风险

        Returns:
            Dict: 组合风险信息
                - total_value: 总资产
                - cumulative_return: 累计收益率
                - portfolio_stop_loss_triggered: 是否触发组合止损
        """
        account = self.repo.get_account(self.account_name)
        if not account:
            logger.warning(f"账户 {self.account_name} 不存在")
            return {}

        total_value = float(account.total_value or 0)
        cumulative_return = float(account.cumulative_return or 0)
        initial_capital = self.config.get('initial_capital', 100000)

        logger.info(f"\n组合级风险:")
        logger.info(f"  总资产: ¥{total_value:,.2f}")
        logger.info(f"  累计收益: {cumulative_return:+.2%}")

        portfolio_stop_loss_triggered = cumulative_return <= self.portfolio_stop_loss

        if portfolio_stop_loss_triggered:
            logger.warning(f"🚨 触发组合止损: {cumulative_return:.2%} <= {self.portfolio_stop_loss:.2%}")

        return {
            'total_value': total_value,
            'cumulative_return': cumulative_return,
            'initial_capital': initial_capital,
            'portfolio_stop_loss_triggered': portfolio_stop_loss_triggered,
            'portfolio_stop_loss_threshold': self.portfolio_stop_loss
        }

    def execute_stop_loss(self, stop_loss_list: List[Dict], trade_date: str):
        """执行止损卖出

        Args:
            stop_loss_list: 触发止损的股票列表
            trade_date: 交易日期
        """
        if not self.auto_execute:
            logger.info("自动止损已禁用，仅发送告警")
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"执行止损卖出: {len(stop_loss_list)}只股票")
        logger.info(f"{'='*60}")

        # 创建交易器实例
        trader = SimulationTrader(
            account_name=self.account_name,
            factor_calculator=self.config['model'].get('factor_calculator', 'v13')
        )

        # 执行止损
        prices = {item['symbol']: item['current_price'] for item in stop_loss_list}
        symbols = [item['symbol'] for item in stop_loss_list]

        trader._execute_stop_loss(symbols, prices, trade_date)
        trader._save_account_to_db()

        logger.info(f"✅ 止损卖出完成")

    def send_notification(self, stop_loss_list: List[Dict], portfolio_risk: Dict):
        """发送风险告警通知

        Args:
            stop_loss_list: 触发止损的股票列表
            portfolio_risk: 组合风险信息
        """
        if not stop_loss_list and not portfolio_risk.get('portfolio_stop_loss_triggered'):
            logger.info("无风险告警，跳过通知")
            return

        # 构建告警消息
        title = f"{self.strategy_name.upper()} 风险告警"

        lines = [f"**策略**: {self.strategy_name}"]
        lines.append(f"**账户**: {self.account_name}")
        lines.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 组合级风险
        lines.append("**组合状态**:")
        lines.append(f"• 总资产: ¥{portfolio_risk['total_value']:,.2f}")
        lines.append(f"• 累计收益: {portfolio_risk['cumulative_return']:+.2%}")

        if portfolio_risk.get('portfolio_stop_loss_triggered'):
            lines.append(f"• 🚨 **触发组合止损** (阈值: {portfolio_risk['portfolio_stop_loss_threshold']:.0%})")

        # 单股止损
        if stop_loss_list:
            lines.append("")
            lines.append(f"**单股止损 ({len(stop_loss_list)}只)**:")
            for item in stop_loss_list:
                lines.append(
                    f"• {item['symbol']} {item['name']}: "
                    f"成本¥{item['avg_cost']:.2f} → 现价¥{item['current_price']:.2f} "
                    f"({item['pnl_pct']:+.2%}), "
                    f"市值¥{item['position_value']:,.0f}"
                )

            if self.auto_execute:
                lines.append("")
                lines.append("**✅ 已自动执行止损卖出**")
            else:
                lines.append("")
                lines.append("**⚠️ 请手动处理止损**")

        message = "\n".join(lines)

        try:
            result = self.notification_facade.send_alert(
                alert_type='risk',
                symbol=f'{self.strategy_name.upper()}策略',
                message=title,
                data={'details': message},
                mention=True
            )

            if result:
                logger.info("✅ 风险告警通知已发送")
            else:
                logger.error("❌ 风险告警通知发送失败")
        except Exception as e:
            logger.error(f"发送风险告警通知异常: {e}")

    def run(self) -> Dict:
        """运行风险检查任务

        Returns:
            Dict: 检查结果
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"{self.strategy_name.upper()} 策略风险检查开始")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")

        try:
            # 1. 检查单股止损
            stop_loss_list = self.check_single_stock_stop_loss()

            # 2. 检查组合级风险
            portfolio_risk = self.check_portfolio_risk()

            # 3. 执行止损（如果启用）
            if stop_loss_list and self.auto_execute:
                trade_date = datetime.now().strftime('%Y-%m-%d')
                self.execute_stop_loss(stop_loss_list, trade_date)

            # 4. 发送通知
            self.send_notification(stop_loss_list, portfolio_risk)

            logger.info(f"\n{'='*70}")
            logger.info(f"✅ {self.strategy_name.upper()} 策略风险检查完成")
            logger.info(f"{'='*70}")

            return {
                'strategy': self.strategy_name,
                'account_name': self.account_name,
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'stop_loss_triggered_count': len(stop_loss_list),
                'stop_loss_list': stop_loss_list,
                'portfolio_risk': portfolio_risk,
                'auto_executed': self.auto_execute and len(stop_loss_list) > 0
            }

        except Exception as e:
            logger.error(f"风险检查失败: {e}", exc_info=True)
            return {
                'strategy': self.strategy_name,
                'account_name': self.account_name,
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


def strategy_risk_check(strategy_name: str, auto_execute: bool = False) -> Dict:
    """单个策略风险检查

    Args:
        strategy_name: 策略名称（如 'v13', 'v14'）
        auto_execute: 是否自动执行止损

    Returns:
        Dict: 检查结果
    """
    checker = StrategyRiskChecker(strategy_name, auto_execute)
    return checker.run()


def strategy_risk_check_all(auto_execute: bool = False) -> Dict:
    """检查所有启用策略的风险

    Args:
        auto_execute: 是否自动执行止损

    Returns:
        Dict: 所有策略的检查结果
    """
    logger.info(f"\n{'='*70}")
    logger.info("所有策略风险检查开始")
    logger.info(f"{'='*70}")

    strategy_service = StrategyService()
    strategies = strategy_service.list_strategies()

    results = {
        'timestamp': datetime.now().isoformat(),
        'strategies_checked': len(strategies),
        'success': True,
        'results': {}
    }

    for strategy_name in strategies:
        logger.info(f"\n检查策略: {strategy_name}")
        result = strategy_risk_check(strategy_name, auto_execute)
        results['results'][strategy_name] = result

        if result['status'] != 'success':
            results['success'] = False

    logger.info(f"\n{'='*70}")
    logger.info(f"✅ 所有策略风险检查完成 (成功: {results['success']})")
    logger.info(f"{'='*70}")

    return results


# ==================== Scheduler 调用入口 ====================

def v13_risk_check(**params) -> Dict:
    """V13风险检查（向后兼容接口）

    这是scheduler调用的入口函数
    """
    auto_execute = params.get('auto_execute', False)
    return strategy_risk_check('v13', auto_execute)


def v14_risk_check(**params) -> Dict:
    """V14风险检查（新接口）"""
    auto_execute = params.get('auto_execute', False)
    return strategy_risk_check('v14', auto_execute)


def all_strategies_risk_check(**params) -> Dict:
    """所有策略风险检查（统一接口）"""
    auto_execute = params.get('auto_execute', False)
    return strategy_risk_check_all(auto_execute)


if __name__ == '__main__':
    """命令行测试"""
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python strategy_risk_check_job.py v13")
        print("  python strategy_risk_check_job.py v14")
        print("  python strategy_risk_check_job.py all")
        sys.exit(1)

    strategy = sys.argv[1]

    if strategy == 'all':
        result = strategy_risk_check_all(auto_execute=False)
    else:
        result = strategy_risk_check(strategy, auto_execute=False)

    if result['status'] == 'success' or result.get('success'):
        print(f"\n✅ 风险检查完成")
        sys.exit(0)
    else:
        print(f"\n❌ 风险检查失败")
        sys.exit(1)
