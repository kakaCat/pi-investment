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
                # 恒生指数
                hsi_df = self.provider_manager.call_akshare('stock_hk_index_spot_em')

                # 港股通成交额
                hk_hold_df = self.provider_manager.call_akshare('stock_hk_hold')

                return {
                    'success': True,
                    'data': {
                        'indices': hsi_df.to_dict('records') if not hsi_df.empty else [],
                        'hk_connect': hk_hold_df.tail(10).to_dict('records') if not hk_hold_df.empty else [],
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
                # 南向资金流向
                df = self.provider_manager.call_akshare('stock_hk_fund_flow_em')

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': '暂无南向资金数据',
                        'data': None
                    }

                self.logger.info(f"南向资金数据: {len(df)} 条")

                return {
                    'success': True,
                    'data': {
                        'flow_data': df.tail(30).to_dict('records'),
                        'total': len(df),
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
                # 港股热门排行
                df = self.provider_manager.call_akshare('stock_hot_rank_em', symbol="港股")

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': '暂无港股人气数据',
                        'data': None
                    }

                self.logger.info(f"港股人气数据: {len(df)} 条")

                return {
                    'success': True,
                    'data': {
                        'hot_stocks': df.head(50).to_dict('records'),
                        'total': len(df),
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
                # 港股K线数据
                df = self.provider_manager.call_akshare('stock_hk_daily', symbol=symbol, adjust="qfq")

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'暂无港股 {symbol} 的技术指标数据',
                        'data': None
                    }

                # 取最近数据
                recent_data = df.tail(60).to_dict('records')

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
                # 港股财务指标
                df = self.provider_manager.call_akshare('stock_financial_hk_analysis_indicator_em', symbol=symbol)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'暂无港股 {symbol} 的财务数据',
                        'data': None
                    }

                financials = df.to_dict('records')

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
