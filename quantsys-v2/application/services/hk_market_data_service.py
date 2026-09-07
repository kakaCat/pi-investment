"""
港股市场数据服务 - v2 原生实现
提供港股市场概览、南向资金、人气排行等数据
"""
import structlog
from datetime import datetime
from typing import Dict, Any
from domain.ports.datasource_ports import IDataProviderManager

logger = structlog.get_logger(__name__)

class HKMarketDataService:
    """港股市场数据服务"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()

    def get_market_overview(self) -> Dict[str, Any]:
        """
        获取港股市场概览

        Returns:
            包含港股市场概览数据的字典
        """
        try:

            self.logger.info("获取港股市场概览")

            try:
                # 2026-09-05 修复：call_akshare 方法不存在，改走
                # DataProviderManager.get_hk_market_overview()。provider 将恒指现货+港股通持股
                # 双数据集包装为单条 record：data=[{'indices': [...], 'hk_connect': [...]}]。
                resp = self.provider_manager.get_hk_market_overview()
                if not resp.get('success') or resp.get('data') is None:
                    return {
                        'success': False,
                        'error': f'暂时无法获取港股市场概览: {resp.get("error", "provider 返回空")}',
                        'data': None
                    }

                records = resp['data'].data  # StockData.data = [{'indices': [...], 'hk_connect': [...]}]
                overview = records[0] if records else {}

                return {
                    'success': True,
                    'data': {
                        'indices': overview.get('indices') or [],
                        'hk_connect': overview.get('hk_connect') or [],
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"港股市场概览获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取港股市场概览: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取港股市场概览失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_south_flow(self) -> Dict[str, Any]:
        """
        获取南向资金流向

        Returns:
            包含南向资金流向数据的字典
        """
        try:

            self.logger.info("获取南向资金流向")

            try:
                # 2026-09-05 修复：call_akshare 方法不存在，改走
                # DataProviderManager.get_south_flow()（provider 返回全量 records，此处 tail(30) 截断）。
                resp = self.provider_manager.get_south_flow()
                if not resp.get('success') or resp.get('data') is None:
                    return {
                        'success': False,
                        'error': '暂无南向资金数据',
                        'data': None
                    }

                records = resp['data'].data or []  # StockData.data = records list
                if not records:
                    return {
                        'success': False,
                        'error': '暂无南向资金数据',
                        'data': None
                    }

                self.logger.info(f"南向资金数据: {len(records)} 条")

                return {
                    'success': True,
                    'data': {
                        'flow_data': records[-30:],
                        'total': len(records),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"南向资金数据获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取南向资金数据: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取南向资金数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_hot_rank(self) -> Dict[str, Any]:
        """
        获取港股人气排行

        Returns:
            包含港股人气排行数据的字典
        """
        try:

            self.logger.info("获取港股人气排行")

            try:
                # 2026-09-05 修复：call_akshare 方法不存在，改走
                # DataProviderManager.get_hk_hot_rank()（provider 返回全量 records，此处 head(50) 截断）。
                resp = self.provider_manager.get_hk_hot_rank()
                if not resp.get('success') or resp.get('data') is None:
                    return {
                        'success': False,
                        'error': '暂无港股人气数据',
                        'data': None
                    }

                records = resp['data'].data or []  # StockData.data = records list
                if not records:
                    return {
                        'success': False,
                        'error': '暂无港股人气数据',
                        'data': None
                    }

                self.logger.info(f"港股人气数据: {len(records)} 条")

                return {
                    'success': True,
                    'data': {
                        'hot_stocks': records[:50],
                        'total': len(records),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"港股人气数据获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取港股人气数据: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取港股人气数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_technical(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股技术指标

        Args:
            symbol: 港股代码

        Returns:
            包含技术指标数据的字典
        """
        try:

            self.logger.info(f"获取港股技术指标: symbol={symbol}")

            try:
                # 2026-09-05 修复：call_akshare 方法不存在，改走
                # DataProviderManager.get_hk_daily()（provider 返回全量前复权 records，此处 tail(60) 截断）。
                resp = self.provider_manager.get_hk_daily(symbol)
                if not resp.get('success') or resp.get('data') is None:
                    return {
                        'success': False,
                        'error': f'暂无港股 {symbol} 的技术指标数据',
                        'data': None
                    }

                records = resp['data'].data or []  # StockData.data = records list
                if not records:
                    return {
                        'success': False,
                        'error': f'暂无港股 {symbol} 的技术指标数据',
                        'data': None
                    }

                # 取最近数据
                recent_data = records[-60:]

                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'klines': recent_data,
                        'total': len(recent_data),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"港股技术指标获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取港股技术指标: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取港股技术指标失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_financials(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股财务数据

        Args:
            symbol: 港股代码

        Returns:
            包含财务数据的字典
        """
        try:

            self.logger.info(f"获取港股财务数据: symbol={symbol}")

            try:
                # 2026-09-05 修复：call_akshare 方法不存在，改走
                # DataProviderManager.get_hk_financials()（provider 返回全量 records）。
                resp = self.provider_manager.get_hk_financials(symbol)
                if not resp.get('success') or resp.get('data') is None:
                    return {
                        'success': False,
                        'error': f'暂无港股 {symbol} 的财务数据',
                        'data': None
                    }

                financials = resp['data'].data or []  # StockData.data = records list
                if not financials:
                    return {
                        'success': False,
                        'error': f'暂无港股 {symbol} 的财务数据',
                        'data': None
                    }

                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'financials': financials,
                        'total': len(financials),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"港股财务数据获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取港股财务数据: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取港股财务数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股分析数据（综合技术和财务）

        Args:
            symbol: 港股代码

        Returns:
            包含分析数据的字典
        """
        self.logger.info(f"获取港股分析数据: symbol={symbol}")

        # 组合技术和财务数据
        technical = self.get_technical(symbol)
        financials = self.get_financials(symbol)

        if not technical.get('success') and not financials.get('success'):
            return {
                'success': False,
                'error': f'暂无港股 {symbol} 的分析数据',
                'data': None
            }

        return {
            'success': True,
            'data': {
                'symbol': symbol,
                'technical': technical.get('data') if technical.get('success') else None,
                'financials': financials.get('data') if financials.get('success') else None,
                'update_time': datetime.now().isoformat()
            }
        }

# 全局实例
hk_market_data_service = HKMarketDataService()
