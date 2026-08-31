"""
风控检查服务

实现标准风控检查：
1. 资金充足性检查
2. 持仓充足性检查
3. 单笔订单限制
4. 仓位集中度检查
5. 行业集中度检查
6. 日内交易次数限制
7. 止损价格合理性验证
"""

from typing import Dict, Any, Optional
import structlog
from datetime import date

from domain.ports import IRiskConfigRepository, IPortfolioRepository, IStockRepository, IKlineRepository, IRiskRepository
from infrastructure.services.service_factory import ServiceFactory

logger = structlog.get_logger(__name__)


class RiskCheckService:
    """风控检查服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        config_name: str = 'default',
        config_repo: Optional[IRiskConfigRepository] = None,
        portfolio_repo: Optional[IPortfolioRepository] = None,
        stock_repo: Optional[IStockRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        risk_repo: Optional[IRiskRepository] = None,
    ):
        """初始化服务

        Args:
            config_name: 配置名称
            config_repo: 风控配置仓库（可选）
            portfolio_repo: PortfolioRepository（可选）
            stock_repo: StockRepository（可选）
            kline_repo: KlineRepository（可选）
            risk_repo: RiskRepository（可选）
        """
        self.portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
        self.stock_repo = stock_repo or ServiceFactory.get_stock_repository()
        self.kline_repo = kline_repo or ServiceFactory.get_kline_repository()
        self.risk_repo = risk_repo or ServiceFactory.get_risk_repository()
        self.config_repo = config_repo
        if self.config_repo:
            self.config = self.config_repo.get_config(config_name)
        else:
            self.config = None

        if not self.config:
            logger.warning(f"风控配置不存在: {config_name}, 使用默认值")
            self.config = self._get_default_config()

    def check_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查信号是否通过风控

        Args:
            signal: 信号数据

        Returns:
            {
                'passed': True/False,
                'reason': '拒绝原因',
                'checks': {...},
                'quantity': 100,
                'warnings': []
            }
        """
        symbol = signal['symbol']
        action = signal['action']

        result = {
            'passed': True,
            'reason': None,
            'checks': {},
            'quantity': None,
            'warnings': []
        }

        try:
            # 获取当前价格
            latest_kline = self.kline_repo.get_latest_daily_kline(symbol)
            if not latest_kline:
                return self._fail_result('无法获取股票价格')

            current_price = float(latest_kline['close'])

            # 获取账户信息
            account = self.risk_repo.get_latest_balance()
            if not account:
                return self._fail_result('无法获取账户信息')

            # 计算交易数量（在检查之前）
            if action == 'buy':
                quantity = self._calculate_buy_quantity(signal, current_price, account)
            else:
                quantity = self._calculate_sell_quantity(signal)

            # 将计算的数量添加到signal副本中用于检查
            signal_with_quantity = signal.copy()
            signal_with_quantity['quantity'] = quantity

            # 执行各项检查
            if action == 'buy':
                checks = [
                    self._check_funds(signal_with_quantity, current_price, account),
                    self._check_single_order_limit(signal_with_quantity, current_price, account),
                    self._check_position_concentration(symbol, current_price, account, signal_with_quantity),
                    self._check_sector_concentration(symbol, current_price, account, signal_with_quantity),
                    self._check_daily_trade_limit(symbol),
                    self._check_stop_loss(signal, current_price, action)
                ]
            else:
                checks = [
                    self._check_holding(signal_with_quantity),
                    self._check_daily_trade_limit(symbol)
                ]

            # 汇总检查结果
            for check in checks:
                check_name = check['check_name']
                result['checks'][check_name] = check

                if not check['passed']:
                    result['passed'] = False
                    result['reason'] = check.get('reason', '风控检查不通过')
                    return result

                if check.get('warning'):
                    result['warnings'].append(check['warning'])

            # 设置最终数量
            result['quantity'] = quantity

            return result

        except Exception as e:
            logger.error(f"风控检查异常: {str(e)}", exc_info=True)
            return self._fail_result(f'检查异常: {str(e)}')

    def _fail_result(self, reason: str) -> Dict:
        """返回失败结果"""
        return {
            'passed': False,
            'reason': reason,
            'checks': {},
            'quantity': None,
            'warnings': []
        }

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'max_single_order_percent': 20.0,
            'min_cash_reserve_percent': 10.0,
            'max_position_percent': 30.0,
            'max_sector_percent': 40.0,
            'max_single_stock_trades': 5,
            'require_stop_loss': True,
            'min_stop_loss_percent': 3.0,
            'max_stop_loss_percent': 15.0
        }

    def _check_funds(
        self,
        signal: Dict,
        current_price: float,
        account: Dict
    ) -> Dict:
        """检查资金充足性"""
        available_cash = float(account.get('cash', 0))

        quantity = signal.get('quantity', 100)

        # 计算成本（股票金额 + 佣金）
        COMMISSION_RATE = 0.0003
        stock_amount = current_price * quantity
        commission = stock_amount * COMMISSION_RATE
        total_cost = stock_amount + commission

        # 检查最低现金储备
        total_assets = float(account.get('total_assets', available_cash))
        min_reserve_percent = float(self.config['min_cash_reserve_percent'])
        min_reserve = total_assets * (min_reserve_percent / 100)
        available_for_trade = available_cash - min_reserve

        if total_cost > available_for_trade:
            return {
                'check_name': 'funds_check',
                'passed': False,
                'reason': f'资金不足: 需要¥{total_cost:.2f}, 可用¥{available_for_trade:.2f}'
            }

        return {
            'check_name': 'funds_check',
            'passed': True,
            'available_cash': available_cash,
            'required_cash': total_cost
        }

    def _check_holding(self, signal: Dict) -> Dict:
        """检查持仓充足性（卖出时）"""
        symbol = signal['symbol']
        quantity = signal.get('quantity', 100)

        holding = self.portfolio_repo.get_holding(symbol)
        if not holding:
            return {
                'check_name': 'holding_check',
                'passed': False,
                'reason': f'无持仓: {symbol}'
            }

        available_quantity = int(holding.get('quantity', 0))
        if available_quantity < quantity:
            return {
                'check_name': 'holding_check',
                'passed': False,
                'reason': f'持仓不足: 可用{available_quantity}股, 需要{quantity}股'
            }

        return {
            'check_name': 'holding_check',
            'passed': True,
            'available_quantity': available_quantity
        }

    def _check_single_order_limit(
        self,
        signal: Dict,
        current_price: float,
        account: Dict
    ) -> Dict:
        """检查单笔订单金额上限"""
        quantity = signal.get('quantity', 100)
        order_amount = current_price * quantity

        total_assets = float(account.get('total_assets', 0))
        max_order_percent = float(self.config['max_single_order_percent'])
        max_order_amount = total_assets * (max_order_percent / 100)

        if order_amount > max_order_amount:
            return {
                'check_name': 'single_order_limit',
                'passed': False,
                'reason': f'单笔订单超限: ¥{order_amount:.2f} > ¥{max_order_amount:.2f}'
            }

        return {
            'check_name': 'single_order_limit',
            'passed': True,
            'order_amount': order_amount,
            'limit_amount': max_order_amount
        }

    def _check_position_concentration(
        self,
        symbol: str,
        current_price: float,
        account: Dict,
        signal: Dict
    ) -> Dict:
        """检查单只股票仓位集中度"""
        holding = self.portfolio_repo.get_holding(symbol)
        current_position_value = 0

        if holding:
            current_quantity = int(holding.get('quantity', 0))
            current_position_value = current_quantity * current_price

        new_quantity = signal.get('quantity', 100)
        new_position_value = current_position_value + (new_quantity * current_price)

        total_assets = float(account.get('total_assets', 0))
        position_percent = (new_position_value / total_assets) * 100 if total_assets > 0 else 0

        max_percent = float(self.config['max_position_percent'])

        if position_percent > max_percent:
            return {
                'check_name': 'position_concentration',
                'passed': False,
                'reason': f'仓位超限: {symbol} 将占{position_percent:.2f}% > {max_percent}%'
            }

        warning = None
        if position_percent > max_percent * 0.8:
            warning = f'{symbol}仓位接近上限: {position_percent:.2f}%'

        return {
            'check_name': 'position_concentration',
            'passed': True,
            'position_percent': position_percent,
            'warning': warning
        }

    def _check_sector_concentration(
        self,
        symbol: str,
        current_price: float,
        account: Dict,
        signal: Dict
    ) -> Dict:
        """检查行业集中度"""
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            return {
                'check_name': 'sector_concentration',
                'passed': True,
                'warning': '无法获取行业信息，跳过行业集中度检查'
            }

        sector = stock.get('industry', 'Unknown')

        holdings = self.portfolio_repo.get_all_holdings()

        sector_value = 0
        for h in holdings:
            h_stock = self.stock_repo.get_by_symbol(h['symbol'])
            if h_stock and h_stock.get('industry') == sector:
                h_kline = self.kline_repo.get_latest_daily_kline(h['symbol'])
                if h_kline:
                    h_price = float(h_kline['close'])
                    sector_value += h['quantity'] * h_price

        new_quantity = signal.get('quantity', 100)
        new_sector_value = sector_value + (new_quantity * current_price)

        total_assets = float(account.get('total_assets', 0))
        sector_percent = (new_sector_value / total_assets) * 100 if total_assets > 0 else 0

        max_percent = float(self.config['max_sector_percent'])

        if sector_percent > max_percent:
            return {
                'check_name': 'sector_concentration',
                'passed': False,
                'reason': f'行业仓位超限: {sector} 将占{sector_percent:.2f}% > {max_percent}%'
            }

        return {
            'check_name': 'sector_concentration',
            'passed': True,
            'sector': sector,
            'sector_percent': sector_percent
        }

    def _check_daily_trade_limit(self, symbol: str) -> Dict:
        """检查日内交易次数限制"""
        today = date.today()

        # 使用PostgreSQL函数查询
        cursor = None
        try:
            cursor = self.portfolio_repo._get_cursor()
            cursor.execute(
                "SELECT * FROM quant.get_trades_by_date_and_symbol(%s, %s)",
                (today, symbol)
            )
            trades_today = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()

        trade_count = len(trades_today)
        max_trades = int(self.config['max_single_stock_trades'])

        if trade_count >= max_trades:
            return {
                'check_name': 'daily_trade_limit',
                'passed': False,
                'reason': f'日内交易次数超限: {symbol} 今日已交易{trade_count}次 >= {max_trades}次'
            }

        return {
            'check_name': 'daily_trade_limit',
            'passed': True,
            'trade_count': trade_count
        }

    def _check_stop_loss(
        self,
        signal: Dict,
        current_price: float,
        action: str
    ) -> Dict:
        """检查止损价格合理性"""
        require_stop_loss = bool(self.config['require_stop_loss'])
        if not require_stop_loss:
            return {
                'check_name': 'stop_loss_check',
                'passed': True,
                'warning': '未启用强制止损检查'
            }

        risk_mgmt = signal.get('risk_management', {})
        stop_loss = risk_mgmt.get('stop_loss')

        if not stop_loss:
            return {
                'check_name': 'stop_loss_check',
                'passed': False,
                'reason': '缺少止损设置'
            }

        # 解析止损价格
        if isinstance(stop_loss, dict):
            stop_loss_price = stop_loss.get('price')
            stop_loss_percent = stop_loss.get('percent')
        else:
            stop_loss_price = None
            stop_loss_percent = None

        # 计算止损幅度
        if stop_loss_price:
            if action == 'buy':
                loss_percent = ((current_price - stop_loss_price) / current_price) * 100
            else:
                loss_percent = ((stop_loss_price - current_price) / current_price) * 100
        elif stop_loss_percent:
            loss_percent = abs(stop_loss_percent)
        else:
            return {
                'check_name': 'stop_loss_check',
                'passed': False,
                'reason': '止损设置格式错误'
            }

        min_percent = float(self.config['min_stop_loss_percent'])
        max_percent = float(self.config['max_stop_loss_percent'])

        if loss_percent < min_percent:
            return {
                'check_name': 'stop_loss_check',
                'passed': False,
                'reason': f'止损幅度过小: {loss_percent:.2f}% < {min_percent}%'
            }

        if loss_percent > max_percent:
            return {
                'check_name': 'stop_loss_check',
                'passed': False,
                'reason': f'止损幅度过大: {loss_percent:.2f}% > {max_percent}%'
            }

        return {
            'check_name': 'stop_loss_check',
            'passed': True,
            'stop_loss_percent': loss_percent
        }

    def _calculate_buy_quantity(
        self,
        signal: Dict,
        current_price: float,
        account: Dict
    ) -> int:
        """计算建议买入数量"""
        if signal.get('quantity'):
            quantity = int(signal['quantity'])
            return (quantity // 100) * 100

        risk_mgmt = signal.get('risk_management', {})
        position_sizing = risk_mgmt.get('position_sizing', {})

        position_percent = position_sizing.get('percent', 10.0)

        total_assets = float(account.get('total_assets', 0))
        target_amount = total_assets * (position_percent / 100)

        quantity = int(target_amount / current_price)

        # Round down to nearest 100-share lot
        quantity = (quantity // 100) * 100

        # Ensure at least 100 shares
        return max(100, quantity)

    def _calculate_sell_quantity(self, signal: Dict) -> int:
        """计算建议卖出数量"""
        if signal.get('quantity'):
            return int(signal['quantity'])

        symbol = signal['symbol']
        holding = self.portfolio_repo.get_holding(symbol)

        if holding:
            return int(holding.get('quantity', 0))

        return 0
