"""
股票数据服务 - v2 原生实现
提供个股公告、新闻、批量行情、内幕交易、同业对比等数据
"""
import structlog
from datetime import datetime
from typing import Dict, Any, List
from adapters.outbound.datasources import get_data_provider_manager

logger = structlog.get_logger(__name__)


class StockDataService:
    """股票数据服务"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.provider_manager = get_data_provider_manager()

    def get_announcements(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票公告

        Args:
            symbol: 股票代码

        Returns:
            包含公告列表的字典
        """
        self.logger.info(f"获取股票公告: symbol={symbol}")

        # Use DataProviderManager for failover
        result = self.provider_manager.get_announcements(symbol)

        if result['success']:
            stock_data = result['data']
            return {
                'success': True,
                'data': {
                    'symbol': stock_data.symbol,
                    'announcements': stock_data.data,
                    'total': stock_data.total,
                    'source': stock_data.source,  # NEW: track data source
                    'update_time': stock_data.timestamp
                }
            }

        return {
            'success': False,
            'error': result.get('error', 'Failed to get announcements'),
            'data': None
        }

    def get_news(self, symbol: str, num: int = 10) -> Dict[str, Any]:
        """
        获取个股新闻

        Args:
            symbol: 股票代码
            num: 返回新闻数量

        Returns:
            包含新闻列表的字典
        """
        self.logger.info(f"获取个股新闻: symbol={symbol}, num={num}")

        # Use DataProviderManager for failover
        result = self.provider_manager.get_news(symbol, num=num)

        if result['success']:
            stock_data = result['data']
            return {
                'success': True,
                'data': {
                    'symbol': stock_data.symbol,
                    'news': stock_data.data,
                    'total': stock_data.total,
                    'source': stock_data.source,  # NEW: track data source
                    'update_time': stock_data.timestamp
                }
            }

        return {
            'success': False,
            'error': result.get('error', 'Failed to get news'),
            'data': None
        }

    def get_batch_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        批量获取股票行情

        Args:
            symbols: 股票代码列表

        Returns:
            包含批量行情数据的字典
        """
        self.logger.info(f"批量获取股票行情: {len(symbols)} 只")

        # Use DataProviderManager with automatic failover per symbol
        quotes = []
        sources_used = set()

        for symbol in symbols:
            result = self.provider_manager.get_quote(symbol)
            if result['success']:
                quote_data = result['data']
                quotes.append({
                    'symbol': quote_data.symbol,
                    'name': quote_data.name,
                    'price': quote_data.price,
                    'open': quote_data.open,
                    'high': quote_data.high,
                    'low': quote_data.low,
                    'volume': quote_data.volume,
                    'change_pct': quote_data.change_pct,
                })
                sources_used.add(quote_data.source)
            else:
                self.logger.warning(f"获取 {symbol} 行情失败")

        if not quotes:
            return {
                'success': False,
                'error': '无法获取任何股票行情',
                'data': None
            }

        self.logger.info(f"批量行情数据: {len(quotes)} 只")

        return {
            'success': True,
            'data': {
                'quotes': quotes,
                'total': len(quotes),
                'sources': list(sources_used),  # NEW: track which sources were used
                'update_time': datetime.now().isoformat()
            }
        }

    def get_insider_trades(self, symbol: str) -> Dict[str, Any]:
        """
        获取内幕交易数据

        Args:
            symbol: 股票代码

        Returns:
            包含内幕交易数据的字典
        """
        try:
            import akshare as ak

            self.logger.info(f"获取内幕交易: symbol={symbol}")

            try:
                # 获取股东增减持数据（作为内幕交易的替代）
                df = ak.stock_dzjy_hygtj(symbol=symbol)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'暂无股票 {symbol} 的内幕交易数据',
                        'data': None
                    }

                self.logger.info(f"内幕交易数据: {len(df)} 条")

                trades = df.to_dict('records')

                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'trades': trades,
                        'total': len(trades),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"内幕交易数据获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取内幕交易数据: {str(e)}',
                    'data': None
                }

        except ImportError:
            return {
                'success': False,
                'error': 'akshare 模块不可用',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"获取内幕交易数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def compare_peers(self, symbol: str) -> Dict[str, Any]:
        """
        同业对比分析（使用腾讯财经，避免代理问题）

        Args:
            symbol: 股票代码

        Returns:
            包含同业对比数据的字典
        """
        try:
            import requests
            import re

            self.logger.info(f"同业对比分析: symbol={symbol}")

            # 转换股票代码格式（600519.SH -> sh600519）
            if symbol.endswith('.SH'):
                code = symbol.split('.')[0]
                tencent_code = f"sh{code}"
            elif symbol.endswith('.SZ'):
                code = symbol.split('.')[0]
                tencent_code = f"sz{code}"
            else:
                code = symbol.split('.')[0] if '.' in symbol else symbol
                if code.startswith('6'):
                    tencent_code = f"sh{code}"
                else:
                    tencent_code = f"sz{code}"

            # 1. 获取股票基本信息（腾讯财经）
            url = f"http://qt.gtimg.cn/q={tencent_code}"
            response = requests.get(
                url,
                timeout=10,
                proxies={'http': None, 'https': None}  # 禁用代理
            )
            response.encoding = 'gbk'

            if not response.text or '""' in response.text:
                return {
                    'success': False,
                    'error': f'无法获取股票 {symbol} 的基本信息（腾讯财经无数据）',
                    'data': None
                }

            # 解析腾讯财经返回的数据
            parts = response.text.split('"')
            if len(parts) < 2:
                return {
                    'success': False,
                    'error': '腾讯财经返回数据格式错误',
                    'data': None
                }

            fields = parts[1].split('~')
            if len(fields) < 10:
                return {
                    'success': False,
                    'error': '腾讯财经返回数据不完整',
                    'data': None
                }

            # 提取股票信息
            stock_info = {
                'name': fields[1],
                'code': fields[2],
                'price': float(fields[3]) if fields[3] else 0.0,
                'prev_close': float(fields[4]) if fields[4] else 0.0,
                'open': float(fields[5]) if fields[5] else 0.0,
            }

            # 2. 简化版：返回股票基本信息
            # 注：行业板块数据需要额外的API，暂时只返回个股信息
            result = {
                'symbol': symbol,
                'stock_info': stock_info,
                'note': '同业对比数据源正在迁移中，当前仅返回个股基本信息',
                'update_time': datetime.now().isoformat()
            }

            return {
                'success': True,
                'data': result
            }

        except requests.exceptions.RequestException as e:
            self.logger.warning(f"腾讯财经请求失败: {e}")
            return {
                'success': False,
                'error': f'网络请求失败: {str(e)}',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"同业对比分析失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }


# 全局实例
stock_data_service = StockDataService()
