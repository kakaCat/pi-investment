"""
Pool Signal Scanner Service - 股票池实时信号扫描

为股票池中的每只股票检测当前买入/卖出信号
"""
import structlog
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class PoolSignalScanner:
    """股票池信号扫描器"""

    def __init__(self, kline_repo, strategy_repo):
        self._kline_repo = kline_repo
        self._strategy_repo = strategy_repo

    @staticmethod
    def _normalize_params(raw) -> dict:
        """parsed_params 归一为 {name: value}：
        dict → 原样；[{name, default, ...}] → {name: default}；
        ['a','b']（仅名字无默认值）→ {}；None/其他 → {}"""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            out = {}
            for item in raw:
                if isinstance(item, dict) and 'name' in item:
                    out[item['name']] = item.get('default')
            return out
        return {}

    def scan_pool_signals(
        self,
        symbols: List[str],
        strategy_id: int,
        lookback_days: int = 60
    ) -> Dict:
        """
        扫描股票池中所有股票的实时信号

        Args:
            symbols: 股票代码列表
            strategy_id: 策略ID
            lookback_days: 回溯天数（用于计算技术指标）

        Returns:
            {
                'buy_signals': [...],   # 有买入信号的股票
                'sell_signals': [...],  # 有卖出信号的股票
                'hold_signals': [...],  # 持币观望的股票
                'errors': [...],        # 检测失败的股票
                'scanned_at': '2026-06-04T15:30:00'
            }
        """
        # 获取策略
        strategy = self._strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        # get_by_id 返回的代码键是 code_content（旧键名 code 不存在——
        # 此前 strategy.get('code','') 恒为空串，exec 空码导致全部股票静默
        # 判 hold，0 信号 0 报错（2026-08-04 信号断流最深一层根因）
        strategy_code = strategy.get('code') or strategy.get('code_content', '')
        strategy_name = strategy.get('name', f'Strategy {strategy_id}')
        # 指标策略代码需要 params（与 strategy_executor 的注入契约一致）；
        # parsed_params 列有三种形态（NULL/名字列表/{name,default}列表），归一为 dict
        strategy_params = self._normalize_params(strategy.get('parsed_params'))

        logger.info(f"Scanning {len(symbols)} symbols with strategy {strategy_name}")

        buy_signals = []
        sell_signals = []
        hold_signals = []
        errors = []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days + 30)

        for symbol in symbols:
            try:
                signal_info = self._check_signal_for_symbol(
                    symbol,
                    strategy_code,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    params=strategy_params,
                )

                if signal_info['error']:
                    errors.append({
                        'symbol': symbol,
                        'error': signal_info['error']
                    })
                elif signal_info['signal'] == 'buy':
                    buy_signals.append(signal_info)
                elif signal_info['signal'] == 'sell':
                    sell_signals.append(signal_info)
                else:
                    hold_signals.append(signal_info)

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                errors.append({
                    'symbol': symbol,
                    'error': str(e)
                })

        return {
            'strategy_id': strategy_id,
            'strategy_name': strategy_name,
            'total_symbols': len(symbols),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'hold_signals': hold_signals,
            'errors': errors,
            'scanned_at': datetime.now().isoformat(),
            'summary': {
                'buy': len(buy_signals),
                'sell': len(sell_signals),
                'hold': len(hold_signals),
                'error': len(errors)
            }
        }

    def _check_signal_for_symbol(
        self,
        symbol: str,
        strategy_code: str,
        start_date: str,
        end_date: str,
        params=None,
    ) -> Dict:
        """
        检查单只股票的信号

        Returns:
            {
                'symbol': '600519.SH',
                'signal': 'buy' | 'sell' | 'hold',
                'current_price': 1850.0,
                'reasons': ['RSI超卖反弹', 'MACD金叉'],
                'indicators': {
                    'rsi': 45.2,
                    'macd': 0.5,
                    'ma5': 1820.0,
                    'volume_ratio': 1.5
                },
                'trade_params': {
                    'stop_loss': 1794.5,  # -3%
                    'take_profit': 1998.0  # +8%
                },
                'trade_date': '2026-06-04',
                'error': None
            }
        """
        try:
            # 获取K线数据（使用get_range方法）
            klines = self._kline_repo.get_range(symbol, start_date, end_date)

            # klines is a Polars DataFrame, check if empty using .is_empty()
            if klines.is_empty() or len(klines) < 20:
                return {
                    'symbol': symbol,
                    'signal': 'hold',
                    'error': 'Insufficient data',
                    'current_price': None,
                    'reasons': [],
                    'indicators': {},
                    'trade_params': {},
                    'trade_date': end_date
                }

            # 转换为Pandas DataFrame（策略代码使用pandas）
            import pandas as pd

            # 将Polars DataFrame转换为Pandas DataFrame
            # Polars会自动处理日期类型，转换时需要转为字符串以避免序列化问题
            df = klines.to_pandas()

            # 将date对象转换为字符串以避免JSON序列化问题
            if 'trade_date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['trade_date']):
                df['trade_date'] = df['trade_date'].astype(str)

            # 执行策略代码获取信号
            signal_result = self._execute_strategy_on_df(df, strategy_code, params=params)

            return {
                'symbol': symbol,
                'signal': signal_result['signal'],
                'current_price': signal_result['current_price'],
                'reasons': signal_result['reasons'],
                'indicators': signal_result['indicators'],
                'trade_params': signal_result['trade_params'],
                'trade_date': signal_result['trade_date'],
                'error': None
            }

        except Exception as e:
            logger.error(f"Error checking signal for {symbol}: {e}")
            return {
                'symbol': symbol,
                'signal': 'hold',
                'error': str(e),
                'current_price': None,
                'reasons': [],
                'indicators': {},
                'trade_params': {},
                'trade_date': end_date
            }

    def _execute_strategy_on_df(self, df, strategy_code: str, params=None) -> Dict:
        """
        在DataFrame上执行策略代码，获取最新信号

        这是核心逻辑，执行策略代码并返回最后一天的信号
        """
        import pandas as pd
        import numpy as np

        # 执行策略代码（添加buy/sell列）；params 注入与 strategy_executor 契约一致
        local_vars = {'df': df, 'pd': pd, 'np': np, 'params': params}
        exec(strategy_code, {}, local_vars)
        df = local_vars['df']

        # 获取最后一行（最新数据）
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else last_row

        # 计算技术指标（如果策略代码中已计算）
        indicators = {}
        for col in ['rsi', 'rsi14', 'macd', 'ma5', 'volume_ratio']:
            if col in df.columns and not pd.isna(last_row.get(col)):
                indicators[col] = float(last_row[col])

        # 判断信号
        signal = 'hold'
        reasons = []

        if 'buy' in df.columns and last_row.get('buy', False):
            signal = 'buy'
            # 根据指标推断买入理由
            if indicators.get('rsi14', 100) < 50:
                reasons.append('RSI超卖区间')
            if indicators.get('macd', 0) > 0:
                reasons.append('MACD金叉')
            if not reasons:
                reasons.append('策略买入信号')

        elif 'sell' in df.columns and last_row.get('sell', False):
            signal = 'sell'
            reasons.append('策略卖出信号')

        current_price = float(last_row['close'])

        # 计算交易参数
        trade_params = {}
        if signal == 'buy':
            trade_params = {
                'stop_loss': round(current_price * 0.97, 2),    # -3%
                'take_profit': round(current_price * 1.08, 2),  # +8%
                'suggested_position': 0.10  # 建议仓位10%
            }

        return {
            'signal': signal,
            'current_price': current_price,
            'reasons': reasons,
            'indicators': indicators,
            'trade_params': trade_params,
            'trade_date': last_row.get('trade_date', str(datetime.now().date()))
        }
