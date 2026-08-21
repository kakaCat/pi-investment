"""
技术分析服务 - v2 原生实现
提供价格行为分析、买入区间计算、退出计划、K线形态分析
"""
import structlog
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = structlog.get_logger(__name__)


class TechnicalAnalysisService:
    """技术分析服务"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    def _get_klines_df(self, symbol: str, period_days: int = 60) -> Optional['pd.DataFrame']:
        """通过 DataProviderManager 获取K线数据并转为 DataFrame

        Args:
            symbol: 股票代码（6位数字）
            period_days: 获取多少天的数据

        Returns:
            pandas DataFrame（中文列名，与 akshare 格式兼容）或 None
        """
        import pandas as pd
        from adapters.outbound.datasources.manager import get_data_provider_manager

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')

        manager = get_data_provider_manager()
        result = manager.get_klines(symbol, 'daily', start_date, end_date)

        if not result.get('success') or not result.get('data'):
            return None

        klines = result['data']
        if not klines or len(klines) == 0:
            return None

        # 将 KlineData 列表转为 DataFrame，使用中文列名兼容现有逻辑
        records = []
        for k in klines:
            records.append({
                '日期': k.date,
                '开盘': k.open,
                '收盘': k.close,
                '最高': k.high,
                '最低': k.low,
                '成交量': k.volume,
                '成交额': k.amount,
                '涨跌幅': k.change_pct,
            })

        df = pd.DataFrame(records)
        # 按日期排序
        df = df.sort_values('日期').reset_index(drop=True)
        return df

    def analyze_price_action(self, symbol: str, period: int = 60) -> Dict[str, Any]:
        """
        价格行为分析

        Args:
            symbol: 股票代码
            period: 分析周期（天数）

        Returns:
            包含价格行为分析结果的字典
        """
        try:
            import pandas as pd

            self.logger.info(f"价格行为分析: symbol={symbol}, period={period}")

            try:
                # 获取历史K线数据（通过 DataProviderManager）
                df = self._get_klines_df(symbol, period_days=period + 10)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'无法获取股票 {symbol} 的K线数据',
                        'data': None
                    }

                # 取最近period天的数据
                df = df.tail(period)

                # 计算价格行为指标
                df['ma5'] = df['收盘'].rolling(window=5).mean()
                df['ma10'] = df['收盘'].rolling(window=10).mean()
                df['ma20'] = df['收盘'].rolling(window=20).mean()

                latest = df.iloc[-1]

                # 安全解析涨跌幅
                raw_change_pct = latest['涨跌幅']
                try:
                    change_pct = float(raw_change_pct) if pd.notna(raw_change_pct) else 0.0
                    # 验证数据合理性
                    if abs(change_pct) > 30:
                        change_pct = 0.0
                except (ValueError, TypeError):
                    change_pct = 0.0

                analysis = {
                    'symbol': symbol,
                    'current_price': float(latest['收盘']),
                    'ma5': float(latest['ma5']) if pd.notna(latest['ma5']) else None,
                    'ma10': float(latest['ma10']) if pd.notna(latest['ma10']) else None,
                    'ma20': float(latest['ma20']) if pd.notna(latest['ma20']) else None,
                    'volume': int(latest['成交量']) if pd.notna(latest['成交量']) else 0,
                    'change_pct': change_pct,
                    'period': period,
                    'update_time': datetime.now().isoformat()
                }

                return {
                    'success': True,
                    'data': analysis
                }

            except Exception as e:
                self.logger.warning(f"价格行为分析失败: {e}")
                return {
                    'success': False,
                    'error': f'价格行为分析失败: {str(e)}',
                    'data': None
                }

        except ImportError:
            return {
                'success': False,
                'error': 'pandas 模块不可用',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"价格行为分析失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def calculate_buy_range(self, symbol: str) -> Dict[str, Any]:
        """
        计算买入区间（使用多数据源 failover）

        Args:
            symbol: 股票代码

        Returns:
            包含买入区间建议的字典
        """
        try:
            import pandas as pd
            from domain.ports import IKlineRepository

            self.logger.info(f"计算买入区间: symbol={symbol}")

            # 使用 KlineRepository 从数据库获取历史数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

            kline_repo = IKlineRepository()
            # 确保 symbol 有后缀
            if '.' not in symbol:
                symbol_with_suffix = symbol + ('.SH' if symbol.startswith('6') else '.SZ')
            else:
                symbol_with_suffix = symbol

            klines = kline_repo.get_daily_klines(symbol_with_suffix, start_date, end_date)

            if klines is None or klines.is_empty():
                return {
                    'success': False,
                    'error': f'股票 {symbol} 没有历史数据',
                    'data': None
                }

            # 将 Polars DataFrame 转换为 Pandas DataFrame
            df = klines.to_pandas()

            if df.empty:
                return {
                    'success': False,
                    'error': f'股票 {symbol} 没有历史数据',
                    'data': None
                }

            # 计算买入区间（基于布林带）
            df = df.tail(60)
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['std20'] = df['close'].rolling(window=20).std()
            df['upper'] = df['ma20'] + 2 * df['std20']
            df['lower'] = df['ma20'] - 2 * df['std20']

            latest = df.iloc[-1]
            current_price = float(latest['close'])

            buy_range = {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'lower_bound': round(float(latest['lower']) if pd.notna(latest['lower']) else current_price * 0.95, 2),
                'upper_bound': round(float(latest['upper']) if pd.notna(latest['upper']) else current_price * 1.05, 2),
                'ma20': round(float(latest['ma20']) if pd.notna(latest['ma20']) else current_price, 2),
                'recommendation': 'hold',  # 简化版，实际应根据价格位置判断
                'update_time': datetime.now().isoformat()
            }

            return {
                'success': True,
                'data': buy_range
            }

        except ImportError as e:
            self.logger.error(f"模块导入失败: {e}")
            return {
                'success': False,
                'error': f'模块导入失败: {str(e)}',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"买入区间计算失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'买入区间计算失败: {str(e)}',
                'data': None
            }

    def get_exit_plan(self, symbol: str, entry_price: Optional[float] = None) -> Dict[str, Any]:
        """
        获取退出计划

        Args:
            symbol: 股票代码
            entry_price: 入场价格（可选）

        Returns:
            包含退出计划的字典
        """
        try:

            self.logger.info(f"获取退出计划: symbol={symbol}, entry_price={entry_price}")

            try:
                # 使用 KlineRepository 从数据库获取历史数据
                from domain.ports import IKlineRepository

                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

                # 确保 symbol 有后缀
                if '.' not in symbol:
                    symbol_with_suffix = symbol + ('.SH' if symbol.startswith('6') else '.SZ')
                else:
                    symbol_with_suffix = symbol

                kline_repo = IKlineRepository()
                klines = kline_repo.get_daily_klines(symbol_with_suffix, start_date, end_date)

                if not klines or len(klines) == 0:
                    return {
                        'success': False,
                        'error': f'无法获取股票 {symbol} 的数据',
                        'data': None
                    }

                latest = klines[-1]
                current_price = float(latest.get('close', 0))

                if entry_price is None:
                    entry_price = current_price

                # 简化版退出计划
                exit_plan = {
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'profit_pct': ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0,
                    'stop_loss': entry_price * 0.92,  # 8% 止损
                    'take_profit_1': entry_price * 1.10,  # 10% 止盈
                    'take_profit_2': entry_price * 1.20,  # 20% 止盈
                    'update_time': datetime.now().isoformat()
                }

                return {
                    'success': True,
                    'data': exit_plan
                }

            except Exception as e:
                self.logger.warning(f"退出计划获取失败: {e}")
                return {
                    'success': False,
                    'error': f'退出计划获取失败: {str(e)}',
                    'data': None
                }

        except ImportError:
            return {
                'success': False,
                'error': '模块不可用',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"退出计划获取失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def analyze_candlestick(self, symbol: str, period: int = 30) -> Dict[str, Any]:
        """
        K线形态分析

        Args:
            symbol: 股票代码
            period: 分析周期（天数）

        Returns:
            包含K线形态分析结果的字典
        """
        try:
            import pandas as pd

            self.logger.info(f"K线形态分析: symbol={symbol}, period={period}")

            try:
                # 获取K线数据（通过 DataProviderManager）
                df = self._get_klines_df(symbol, period_days=period + 5)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'无法获取股票 {symbol} 的K线数据',
                        'data': None
                    }

                df = df.tail(period)
                latest = df.iloc[-1]
                patterns = []

                # 检测十字星
                if abs(float(latest['收盘']) - float(latest['开盘'])) < 0.01 * float(latest['收盘']):
                    patterns.append('十字星')

                # 检测趋势
                if len(df) >= 5:
                    ma5 = df['收盘'].tail(5).mean()
                    if latest['收盘'] > ma5:
                        patterns.append('上升趋势')
                    else:
                        patterns.append('下降趋势')

                analysis = {
                    'symbol': symbol,
                    'patterns': patterns,
                    'current_price': float(latest['收盘']),
                    'open': float(latest['开盘']),
                    'high': float(latest['最高']),
                    'low': float(latest['最低']),
                    'volume': int(latest['成交量']) if pd.notna(latest['成交量']) else 0,
                    'period': period,
                    'update_time': datetime.now().isoformat()
                }

                return {
                    'success': True,
                    'data': analysis
                }

            except Exception as e:
                self.logger.warning(f"K线形态分析失败: {e}")
                return {
                    'success': False,
                    'error': f'K线形态分析失败: {str(e)}',
                    'data': None
                }

        except ImportError:
            return {
                'success': False,
                'error': 'pandas 模块不可用',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"K线形态分析失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }


# 全局实例
technical_analysis_service = TechnicalAnalysisService()
