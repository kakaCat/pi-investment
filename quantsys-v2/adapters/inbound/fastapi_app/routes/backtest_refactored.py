# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file


# Extracted Constants


# Extracted Constants

CONST_400 = 400

CONST_500 = 500



CONST_400 = 400

CONST_500 = 500



"""
回测路由重构 - 降低 run_backtest 复杂度

将原有的 run_backtest 函数（复杂度 37）拆分为多个小函数
"""

from typing import Dict, Any, Optional, List, Tuple
from fastapi import Body
import logging

logger = logging.getLogger(__name__)


class BacktestRequestProcessor:
    """回测请求处理器"""

    def __init__(self, raw_data: Dict[str, Any]):
        self.data = self._convert_keys(raw_data)

    def _convert_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """转换键名为 snake_case"""
        from adapters.shared.response_utils import convert_keys_to_snake
        return convert_keys_to_snake(data)

    def normalize_strategy_name(self) -> Optional[str]:
        """标准化策略名称

        Returns:
            错误消息，成功时返回 None
        """
        # strategy -> strategy_name
        if 'strategy' in self.data and 'strategy_name' not in self.data:
            self.data['strategy_name'] = self.data['strategy']

        # indicator_id -> strategy_name
        if 'indicator_id' in self.data and 'strategy_name' not in self.data:
            try:
                indicator_id = int(self.data['indicator_id'])
                self.data['strategy_name'] = f"indicator_{indicator_id}"
            except (ValueError, TypeError) as e:
                return f'无效的 indicator_id: {e}'

        # strategy_id -> strategy_name
        if 'strategy_id' in self.data and 'strategy_name' not in self.data:
            error = self._resolve_strategy_id()
            if error:
                return error

        return None

    def _resolve_strategy_id(self) -> Optional[str]:
        """解析 strategy_id 为 strategy_name"""
        try:
            from infrastructure.services.service_factory import ServiceFactory
            strategy_service = ServiceFactory.get_strategy_service()

            strat = strategy_service.get_strategy(int(self.data['strategy_id']))
            if not strat:
                return f'策略不存在: {self.data["strategy_id"]}'

            self.data['strategy_name'] = strat.get('name') or f"strategy_{self.data['strategy_id']}"
            return None
        except (ValueError, TypeError) as e:
            return f'无效的 strategy_id: {e}'

    def normalize_parameters(self) -> None:
        """标准化参数"""
        # params -> parameters
        if 'parameters' not in self.data and isinstance(self.data.get('params'), dict):
            self.data['parameters'] = self.data['params']

        # 展开 parameters
        if 'parameters' in self.data and isinstance(self.data['parameters'], dict):
            self._expand_parameters()

        # initial_cash -> initial_capital
        if 'initial_cash' in self.data and 'initial_capital' not in self.data:
            self.data['initial_capital'] = self.data['initial_cash']

    def _expand_parameters(self) -> None:
        """展开 parameters 对象到顶层"""
        params = self.data['parameters']

        param_mappings = {
            'fast_period': 'ma_short',
            'slow_period': 'ma_long',
            'short_period': 'ma_short',
            'long_period': 'ma_long',
            'rsi_period': 'rsi_period',
            'pe_heavy_buy': 'pe_heavy_buy',
            'pe_batch_buy': 'pe_batch_buy',
            'pe_reduce': 'pe_reduce',
            'pe_liquidate': 'pe_liquidate',
            'eps_start': 'eps_start',
            'eps_end': 'eps_end',
            'stop_loss_pct': 'stop_loss_pct',
            'take_profit_pct': 'take_profit_pct',
            'dividend_yield': 'dividend_yield',
            'pb_heavy_buy': 'pb_heavy_buy',
            'pb_batch_buy': 'pb_batch_buy',
            'pb_reduce': 'pb_reduce',
            'pb_liquidate': 'pb_liquidate',
            'roe_mean': 'roe_mean',
        }

        for source_key, target_key in param_mappings.items():
            if source_key in params and target_key not in self.data:
                self.data[target_key] = params[source_key]

        del self.data['parameters']
        self.data.pop('params', None)

    def validate_required_fields(self) -> Optional[str]:
        """验证必需字段

        Returns:
            错误消息，成功时返回 None
        """
        required = ['strategy_name', 'symbol', 'start_date', 'end_date', 'initial_capital']

        for field in required:
            if field not in self.data:
                return f'缺少必需参数: {field}'

        return None

    def validate_strategy_parameters(self) -> Optional[str]:
        """验证策略特定参数

        Returns:
            错误消息，成功时返回 None
        """
        strategy_name = self.data['strategy_name'].lower()

        # 指标策略不需要额外参数
        if 'indicator' in strategy_name:
            return None

        # 移动平均策略
        if 'ma' in strategy_name or 'cross' in strategy_name:
            if 'ma_short' not in self.data:
                return '移动平均策略缺少参数: ma_short (或 fastPeriod)'
            if 'ma_long' not in self.data:
                return '移动平均策略缺少参数: ma_long (或 slowPeriod)'

        # RSI 策略
        elif 'rsi' in strategy_name:
            if 'rsi_period' not in self.data:
                return 'RSI策略缺少参数: rsi_period (或 rsiPeriod)'

        return None

    def get_klines(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """获取 K 线数据

        Returns:
            (K线数据列表, 错误消息)
        """
        try:
            import polars as pl
            from infrastructure.services.service_factory import ServiceFactory

            kline_repo = ServiceFactory.get_kline_repository()

            symbol = self.data['symbol']
            start_date = self.data['start_date']
            end_date = self.data['end_date']

            klines_df = kline_repo.get_daily_klines(symbol, start_date, end_date)

            if isinstance(klines_df, pl.DataFrame) and not klines_df.is_empty():
                klines = klines_df.to_dicts()
            else:
                klines = []

            if not klines:
                return None, '没有K线数据'

            return klines, None

        except Exception as e:
            logger.exception("获取K线数据失败")
            return None, f'获取K线数据失败: {str(e)}'

    def run_backtest(self, klines: List[Dict]) -> Dict[str, Any]:
        """运行回测

        Args:
            klines: K线数据

        Returns:
            回测结果
        """
        from adapters.shared.backtest_helpers import (
            save_simple_backtest,
            run_pe_mean_reversion_backtest,
            run_pb_mean_reversion_backtest,
        )

        strategy_name = self.data['strategy_name'].lower()
        initial_capital = float(self.data['initial_capital'])

        # PE 均值回归
        if 'pe' in strategy_name and 'mean' in strategy_name:
            return run_pe_mean_reversion_backtest(self.data, klines, initial_capital)

        # PB 均值回归
        elif 'pb' in strategy_name and 'mean' in strategy_name:
            return run_pb_mean_reversion_backtest(self.data, klines, initial_capital)

        # 其他策略
        else:
            return save_simple_backtest(self.data, klines, initial_capital)


def run_backtest_endpoint(payload: Optional[Dict[str, Any]] = Body(None)):
    """运行回测端点 - 重构版本（复杂度 < 15）

    支持 strategy_name、strategy_id 或 indicator_id

    复杂度分析：
    - 主函数: 8 (if/return 分支)
    - BacktestRequestProcessor 各方法: 均 < 10
    """
    from adapters.shared.response_utils import (
        error_response,
        convert_keys_to_camel,
        sanitize_for_json,
    )

    # 初始化处理器
    raw_data = payload or {}
    processor = BacktestRequestProcessor(raw_data)

    # 1. 标准化策略名称
    error = processor.normalize_strategy_name()
    if error:
        return error_response({'error': error}, 400)

    # 2. 标准化参数
    processor.normalize_parameters()

    # 3. 验证必需字段
    error = processor.validate_required_fields()
    if error:
        return error_response({'error': error}, 400)

    # 4. 验证策略参数
    error = processor.validate_strategy_parameters()
    if error:
        return error_response({'error': error}, 400)

    # 5. 获取 K 线数据
    klines, error = processor.get_klines()
    if error:
        return error_response({'error': error}, 400)

    # 6. 运行回测
    try:
        result = processor.run_backtest(klines)
        result = convert_keys_to_camel(result)
        return sanitize_for_json(result)
    except Exception as e:
        logger.exception("回测执行失败")
        return error_response({'error': str(e)}, 500)

    # 总复杂度: 8（6个 if + 1个 except + 1个主流程）
