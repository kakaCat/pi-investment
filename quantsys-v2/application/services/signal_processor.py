"""
信号处理服务

统一处理策略信号，提取和计算风控参数。
"""
import structlog
import time
from typing import Dict, Any

from application.services.data_service import DataService
from application.services.signal_monitoring import signal_monitor
from application.services.strategy_circuit_breaker import StrategyCircuitBreaker

logger = structlog.get_logger(__name__)


class SignalProcessingError(Exception):
    """信号处理错误基类"""
    pass


class InvalidStopLossError(SignalProcessingError):
    """止损价格无效"""
    pass


class InvalidTakeProfitError(SignalProcessingError):
    """止盈价格无效"""
    pass


class InvalidPositionSizeError(SignalProcessingError):
    """仓位计算错误"""
    pass


class SignalProcessor:
    """信号处理器"""

    # 默认风控参数
    DEFAULT_STOP_LOSS_PERCENT = 0.08  # 默认止损 8%
    DEFAULT_POSITION_PERCENT = 0.10   # 默认仓位 10%

    def __init__(self, ds: DataService):
        """
        初始化信号处理器

        Args:
            ds: DataService 实例
        """
        self.ds = ds
        self.circuit_breaker = StrategyCircuitBreaker()

    def process_signal(
        self,
        signal: Dict[str, Any],
        symbol: str,
        current_price: float,
        account_balance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理信号，返回完整的交易参数

        Args:
            signal: 策略信号
            symbol: 股票代码
            current_price: 当前价格
            account_balance: 账户余额

        Returns:
            {
                'action': str,
                'quantity': int,
                'price': float,
                'stop_loss_price': float,
                'take_profit_price': float,
                'reason': str,
                'risk_params': dict,
                'warnings': list
            }
        """
        start_time = time.time()
        strategy_name = signal.get('strategy_name', 'unknown')

        try:
            # 验证信号结构
            self._validate_signal_structure(signal)

            # 熔断检查：如果策略被暂停，拒绝实盘信号
            if not self.circuit_breaker.is_allowed(strategy_name):
                breaker_state = self.circuit_breaker.get_state(strategy_name)
                error_msg = (
                    f"策略 {strategy_name} 已被熔断暂停 (状态: {breaker_state['status']})，"
                    f"原因: {breaker_state.get('reason', '未知')}。"
                    f"仅允许纸面测试，不允许实盘交易。"
                )
                logger.warning(error_msg)

                # 记录熔断拒绝
                signal_monitor.record_signal_processing(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    success=False,
                    duration=time.time() - start_time,
                    warnings=[error_msg]
                )

                raise SignalProcessingError(error_msg)

            logger.info(
                f"Processing signal: symbol={symbol}, action={signal.get('action')}, "
                f"confidence={signal.get('confidence'):.2f}, price={current_price}"
            )

            # 验证价格有效性
            if current_price <= 0:
                raise ValueError(f"Invalid current price: {current_price}")

            result = {
                'action': signal['action'],
                'price': current_price,
                'reason': signal.get('reason', ''),
                'stop_loss_price': None,
                'take_profit_price': None,
                'quantity': 0,
                'risk_params': {},
                'warnings': []
            }

            risk_mgmt = signal.get('risk_management', {})

            # 处理止损
            try:
                result['stop_loss_price'] = self._process_stop_loss(
                    risk_mgmt.get('stop_loss'),
                    current_price,
                    signal['action']
                )
                if risk_mgmt.get('stop_loss'):
                    result['risk_params']['stop_loss'] = risk_mgmt['stop_loss']
            except InvalidStopLossError as e:
                logger.warning(f"Invalid stop loss, using default: {e}")
                result['warnings'].append(f"止损价格无效，使用默认值: {str(e)}")
                result['stop_loss_price'] = self._get_default_stop_loss(
                    current_price, signal['action']
                )

            # 处理止盈
            try:
                result['take_profit_price'] = self._process_take_profit(
                    risk_mgmt.get('take_profit'),
                    current_price,
                    signal['action']
                )
                if risk_mgmt.get('take_profit'):
                    result['risk_params']['take_profit'] = risk_mgmt['take_profit']
            except InvalidTakeProfitError as e:
                logger.warning(f"Invalid take profit: {e}")
                result['warnings'].append(f"止盈价格无效: {str(e)}")

            # 处理仓位计算
            try:
                result['quantity'] = self._calculate_position_size(
                    risk_mgmt.get('position_sizing'),
                    current_price,
                    account_balance,
                    signal.get('indicators', {})
                )
                if risk_mgmt.get('position_sizing'):
                    result['risk_params']['position_sizing'] = risk_mgmt['position_sizing']
            except InvalidPositionSizeError as e:
                logger.warning(f"Invalid position size, using default: {e}")
                result['warnings'].append(f"仓位计算失败，使用默认值: {str(e)}")
                result['quantity'] = self._calculate_default_position(
                    current_price, account_balance
                )

            logger.info(
                f"Signal processed: symbol={symbol}, quantity={result['quantity']}, "
                f"stop_loss={result['stop_loss_price']}, warnings={len(result['warnings'])}"
            )

            # 记录成功的信号处理
            duration = time.time() - start_time
            signal_monitor.record_signal_processing(
                strategy_name=strategy_name,
                symbol=symbol,
                success=True,
                duration=duration,
                warnings=result.get('warnings', [])
            )

            return result

        except Exception as e:
            # 记录失败的信号处理
            duration = time.time() - start_time
            signal_monitor.record_signal_processing(
                strategy_name=strategy_name,
                symbol=symbol,
                success=False,
                duration=duration,
                error=str(e)
            )
            raise

    def _validate_signal_structure(self, signal: Dict[str, Any]):
        """验证信号基础结构"""
        required_fields = ['action', 'confidence', 'reason']
        for field in required_fields:
            if field not in signal:
                raise ValueError(f"Missing required field: {field}")

        if signal['action'] not in ('buy', 'sell', 'hold'):
            raise ValueError(f"Invalid action: {signal['action']}")

        if not 0 <= signal['confidence'] <= 1:
            raise ValueError(f"Invalid confidence: {signal['confidence']}")

    def _process_stop_loss(
        self,
        stop_loss_config: Dict[str, Any],
        current_price: float,
        action: str
    ) -> float:
        """处理止损配置"""
        if not stop_loss_config:
            return self._get_default_stop_loss(current_price, action)

        stop_price = stop_loss_config.get('price')

        if stop_price is None or stop_price <= 0:
            raise InvalidStopLossError(f"Invalid stop loss price: {stop_price}")

        # 验证止损价格合理性
        if action == 'buy':
            if stop_price >= current_price:
                raise InvalidStopLossError(
                    f"Buy stop loss {stop_price} must be below current price {current_price}"
                )
        elif action == 'sell':
            if stop_price <= current_price:
                raise InvalidStopLossError(
                    f"Sell stop loss {stop_price} must be above current price {current_price}"
                )

        return stop_price

    def _process_take_profit(
        self,
        take_profit_config: Dict[str, Any],
        current_price: float,
        action: str
    ) -> float:
        """处理止盈配置"""
        if not take_profit_config:
            return None

        tp_price = take_profit_config.get('price')

        if tp_price is None or tp_price <= 0:
            return None

        # 验证止盈价格合理性
        if action == 'buy':
            if tp_price <= current_price:
                logger.warning(
                    f"Buy take profit {tp_price} should be above current price {current_price}"
                )
        elif action == 'sell':
            if tp_price >= current_price:
                logger.warning(
                    f"Sell take profit {tp_price} should be below current price {current_price}"
                )

        return tp_price

    def _calculate_position_size(
        self,
        sizing_config: Dict[str, Any],
        price: float,
        account_balance: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> int:
        """根据配置计算仓位"""
        if not sizing_config:
            return self._calculate_default_position(price, account_balance)

        method = sizing_config['method']
        value = sizing_config.get('value')
        params = sizing_config.get('params', {})

        total_equity = account_balance.get('total_assets', 1000000)
        available_cash = account_balance.get('cash', total_equity * 0.5)

        if method == 'fixed_shares':
            return int(value)

        elif method == 'fixed_percent':
            target_amount = total_equity * value
            shares = int(target_amount / price)
            return self._round_to_lot(shares)

        elif method == 'kelly':
            from domain.quantlib.engine.position_sizing import KellyPositionSizer
            sizer = KellyPositionSizer(
                win_rate=params['win_rate'],
                profit_loss_ratio=params['profit_loss_ratio'],
                kelly_fraction=params.get('kelly_fraction', 0.25)
            )
            return sizer.calculate_position_size(
                price, available_cash, total_equity
            )

        else:
            raise ValueError(f"Unknown position sizing method: {method}")

    def _calculate_default_position(
        self,
        price: float,
        account_balance: Dict[str, Any],
        percent: float = None
    ) -> int:
        """默认仓位计算（10%）"""
        if percent is None:
            percent = self.DEFAULT_POSITION_PERCENT
        total_equity = account_balance.get('total_assets', 1000000)
        target_amount = total_equity * percent
        shares = int(target_amount / price)
        return self._round_to_lot(shares)

    def _get_default_stop_loss(self, current_price: float, action: str) -> float:
        """获取默认止损价格（-8%）"""
        if action == 'buy':
            return round(current_price * (1 - self.DEFAULT_STOP_LOSS_PERCENT), 2)
        elif action == 'sell':
            return round(current_price * (1 + self.DEFAULT_STOP_LOSS_PERCENT), 2)
        return None

    @staticmethod
    def _round_to_lot(shares: int, lot_size: int = 100) -> int:
        """向下取整到手数"""
        return (shares // lot_size) * lot_size
