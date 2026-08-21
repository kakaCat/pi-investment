"""
财务分析服务 - v2 原生实现
提供财务指标、估值分析、现金流分析、利润表分析、质量筛选
"""
from domain.ports import IFinancialRepository, IKlineRepository
import structlog
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
from domain.ports.datasource_ports import IDataProviderManager

logger = structlog.get_logger(__name__)


class FinancialAnalysisService:
    """财务分析服务"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
            # 延迟导入避免顶层依赖
            from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()

    def get_financial_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        获取财务指标 - 使用多数据源 FinancialDataService + 数据库 fallback

        Args:
            symbol: 股票代码

        Returns:
            包含财务指标的字典
        """
        try:
            self.logger.info(f"获取财务指标: symbol={symbol}")

            # 1. 优先使用 FinancialDataService（多数据源 failover）
            try:
                from application.services.financial_data_service import FinancialDataService

                service = FinancialDataService()
                financial_data = service.get_financial_data(
                    symbol=symbol,
                    statement_type='all',
                    periods=3
                )

                # 计算关键财务指标
                indicators = {}
                if financial_data.income_statement and financial_data.balance_sheet:
                    indicators = self._calculate_indicators_from_statements(
                        financial_data.income_statement[0] if financial_data.income_statement else {},
                        financial_data.balance_sheet[0] if financial_data.balance_sheet else {}
                    )

                self.logger.info(f"通过 FinancialDataService 获取财务指标成功: source={financial_data.source}")
                return {
                    'success': True,
                    'data': {
                        'symbol': financial_data.symbol,
                        'source': financial_data.source,
                        'indicators': indicators,
                        'income_statements': financial_data.income_statement[:3] if financial_data.income_statement else [],
                        'balance_sheets': financial_data.balance_sheet[:3] if financial_data.balance_sheet else [],
                        'update_time': financial_data.timestamp.isoformat() if financial_data.timestamp else datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"FinancialDataService 失败: {e}")

            # 2. Fallback 到数据库（直接查询）
            try:
                
                financial_repo = IFinancialRepository()
                income_data = financial_repo.get_income_statements(symbol, period_type='Y', limit=5)
                balance_data = financial_repo.get_balance_sheets(symbol, period_type='Y', limit=5)

                if income_data and balance_data:
                    indicators = self._calculate_indicators_from_statements(
                        income_data[0] if income_data else {},
                        balance_data[0] if balance_data else {}
                    )

                    self.logger.info(f"从数据库 fallback 获取财务指标成功")
                    return {
                        'success': True,
                        'data': {
                            'symbol': symbol,
                            'source': 'database_fallback',
                            'indicators': indicators,
                            'income_statements': income_data[:3],
                            'balance_sheets': balance_data[:3],
                            'update_time': datetime.now().isoformat()
                        }
                    }
            except Exception as e:
                self.logger.warning(f"数据库 fallback 失败: {e}")

            # 3. 所有方式都失败
            return {
                'success': False,
                'error': f'暂时无法获取股票 {symbol} 的财务指标（所有数据源均不可用）',
                'data': None,
                'suggestion': '建议稍后重试或联系管理员检查数据源配置'
            }

        except Exception as e:
            self.logger.error(f"财务指标获取失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'服务异常: {str(e)}',
                'data': None
            }

    def _calculate_indicators_from_statements(
        self,
        income: Dict[str, Any],
        balance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从财务报表计算关键指标"""
        indicators = {}

        try:
            # ROE (净资产收益率)
            net_profit = income.get('net_profit') or income.get('归属母公司所有者的净利润')
            total_equity = balance.get('total_equity') or balance.get('股东权益合计')
            if net_profit and total_equity and total_equity > 0:
                indicators['roe'] = round((net_profit / total_equity) * 100, 2)

            # 净利润率
            revenue = income.get('total_revenue') or income.get('营业总收入')
            if net_profit and revenue and revenue > 0:
                indicators['net_profit_margin'] = round((net_profit / revenue) * 100, 2)

            # 资产负债率
            total_liabilities = balance.get('total_liabilities') or balance.get('负债合计')
            total_assets = balance.get('total_assets') or balance.get('资产总计')
            if total_liabilities and total_assets and total_assets > 0:
                indicators['debt_ratio'] = round((total_liabilities / total_assets) * 100, 2)

            # 流动比率
            current_assets = balance.get('current_assets') or balance.get('流动资产合计')
            current_liabilities = balance.get('current_liabilities') or balance.get('流动负债合计')
            if current_assets and current_liabilities and current_liabilities > 0:
                indicators['current_ratio'] = round(current_assets / current_liabilities, 2)

        except Exception as e:
            self.logger.warning(f"计算财务指标失败: {e}")

        return indicators

    def get_stock_valuation(self, symbol: str) -> Dict[str, Any]:
        """
        获取估值分析 - 使用多数据源自动 failover

        优先级顺序：
        1. 多数据源估值服务（新浪、东方财富、akshare、腾讯、网易）
        2. 从财务报表 + 股价计算 PE/PB（降级方案）

        Args:
            symbol: 股票代码

        Returns:
            包含估值分析的字典
        """
        try:
            self.logger.info(f"估值分析: symbol={symbol}")

            # 方案1: 优先使用多数据源估值服务（自动 failover）
            try:
                from application.services.valuation_data_service import get_valuation_service

                valuation_service = get_valuation_service()
                result = valuation_service.get_valuation(symbol)

                if result.get('success'):
                    self.logger.info(f"通过多数据源服务获取估值成功: source={result['data']['source']}")
                    return result

            except Exception as e:
                self.logger.warning(f"多数据源估值服务失败: {e}")

            # 方案2: 从财务报表和股价计算 PE/PB（降级方案）
            try:
                                
                financial_repo = IFinancialRepository()
                kline_repo = IKlineRepository()

                # 获取最新股价
                latest_kline = kline_repo.get_latest_daily_kline(symbol)
                if not latest_kline:
                    self.logger.warning(f"无法获取 {symbol} 的最新股价")
                    raise Exception("无最新股价数据")

                current_price = latest_kline.get('close')

                # 获取最新财务数据
                income_data = financial_repo.get_income_statements(symbol, period_type='Y', limit=1)
                balance_data = financial_repo.get_balance_sheets(symbol, period_type='Y', limit=1)

                if income_data and balance_data:
                    income = income_data[0]
                    balance = balance_data[0]

                    valuation = {'current_price': current_price}

                    # 尝试计算 PE (市盈率 = 总市值 / 净利润 或 股价 / 每股收益)
                    net_profit = income.get('parent_net_profit') or income.get('net_profit') or income.get('归属母公司所有者的净利润')

                    # 尝试多个可能的股本字段
                    total_shares = (
                        balance.get('total_share_capital') or
                        balance.get('股本') or
                        balance.get('实收资本(或股本)') or
                        income.get('basic_eps_shares')  # 从利润表获取基本每股收益计算用股数
                    )

                    if net_profit and net_profit > 0:
                        if total_shares:
                            eps = net_profit / total_shares  # 每股收益
                            if eps > 0:
                                valuation['pe'] = round(current_price / eps, 2)
                        else:
                            # 无股本数据，尝试从 basic_eps 反推
                            basic_eps = income.get('basic_eps')
                            if basic_eps and basic_eps > 0:
                                valuation['pe'] = round(current_price / basic_eps, 2)

                    # 尝试计算 PB (市净率 = 股价 / 每股净资产)
                    net_assets = balance.get('total_equity') or balance.get('股东权益合计') or balance.get('所有者权益合计')
                    if net_assets and total_shares and net_assets > 0:
                        bps = net_assets / total_shares  # 每股净资产
                        if bps > 0:
                            valuation['pb'] = round(current_price / bps, 2)

                    if len(valuation) > 1:  # 除了 current_price 还有其他指标
                        self.logger.info(f"从财务报表计算估值成功")
                        return {
                            'success': True,
                            'data': {
                                'symbol': symbol,
                                'valuation': valuation,
                                'source': 'calculated_from_financials',
                                'update_time': datetime.now().isoformat(),
                                'note': 'PE/PB 基于最新年报数据计算，可能与实时动态值有差异'
                            }
                        }

                    # 至少返回股价
                    if current_price:
                        self.logger.info(f"仅获取到股价，无法计算 PE/PB")
                        return {
                            'success': True,
                            'data': {
                                'symbol': symbol,
                                'valuation': valuation,
                                'source': 'price_only',
                                'update_time': datetime.now().isoformat(),
                                'note': '暂无 PE/PB 数据，建议使用实时行情工具'
                            }
                        }

            except Exception as e:
                self.logger.warning(f"从财务报表计算估值失败: {e}")

            # 所有方案都失败
            return {
                'success': False,
                'error': f'无法获取股票 {symbol} 的估值数据（所有数据源均不可用）',
                'data': None,
                'suggestion': '建议使用 data_fetch_stock 工具获取实时行情数据'
            }

        except Exception as e:
            self.logger.error(f"估值分析失败: {e}", exc_info=True)
            error_msg = str(e) if str(e) else '服务异常'
            return {
                'success': False,
                'error': f'估值分析失败: {error_msg}',
                'data': None,
                'suggestion': '建议使用 data_fetch_stock 工具获取实时行情数据'
            }

    def get_cash_flow(self, symbol: str) -> Dict[str, Any]:
        """
        获取现金流分析

        Args:
            symbol: 股票代码

        Returns:
            包含现金流数据的字典
        """
        try:
            self.logger.info(f"现金流分析: symbol={symbol}")

            try:
                # 获取现金流量表
                df = self.provider_manager.call_akshare('stock_cash_flow_sheet_by_report_em', symbol=symbol)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'无法获取股票 {symbol} 的现金流数据',
                        'data': None
                    }

                cash_flow = df.to_dict('records')

                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'cash_flow': cash_flow,
                        'total': len(cash_flow),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"现金流分析失败: {e}")
                return {
                    'success': False,
                    'error': f'现金流分析失败: {str(e)}',
                    'data': None
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'现金流分析异常: {str(e)}',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"现金流分析失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_income_statement(self, symbol: str) -> Dict[str, Any]:
        """
        获取利润表分析

        Args:
            symbol: 股票代码

        Returns:
            包含利润表数据的字典
        """
        try:
            self.logger.info(f"利润表分析: symbol={symbol}")

            try:
                # 获取利润表
                df = self.provider_manager.call_akshare('stock_profit_sheet_by_report_em', symbol=symbol)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'无法获取股票 {symbol} 的利润表数据',
                        'data': None
                    }

                income = df.to_dict('records')

                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'income_statement': income,
                        'total': len(income),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"利润表分析失败: {e}")
                return {
                    'success': False,
                    'error': f'利润表分析失败: {str(e)}',
                    'data': None
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'利润表分析异常: {str(e)}',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"利润表分析失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def screen_stocks_quality(
        self,
        min_roe: Optional[float] = None,
        max_pe: Optional[float] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        质量筛选（高质量股票）

        Args:
            min_roe: 最低ROE
            max_pe: 最高PE
            limit: 返回数量

        Returns:
            包含筛选结果的字典
        """
        try:
            import pandas as pd

            self.logger.info(f"质量筛选: min_roe={min_roe}, max_pe={max_pe}, limit={limit}")

            try:
                # 获取A股实时行情
                df = self.provider_manager.call_akshare('stock_zh_a_spot_em')

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': '无法获取A股行情数据',
                        'data': None
                    }

                # 简化版筛选（基于市盈率等基本指标）
                if '市盈率-动态' in df.columns:
                    # 筛选有效PE
                    df = df[pd.notna(df['市盈率-动态'])]
                    df = df[df['市盈率-动态'] > 0]

                    if max_pe:
                        df = df[df['市盈率-动态'] <= max_pe]

                # 按涨跌幅排序
                if '涨跌幅' in df.columns:
                    df = df.sort_values('涨跌幅', ascending=False)

                stocks = df.head(limit).to_dict('records')

                return {
                    'success': True,
                    'data': {
                        'stocks': stocks,
                        'total': len(stocks),
                        'filters': {
                            'min_roe': min_roe,
                            'max_pe': max_pe,
                            'limit': limit
                        },
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"质量筛选失败: {e}")
                return {
                    'success': False,
                    'error': f'质量筛选失败: {str(e)}',
                    'data': None
                }

        except ImportError:
            return {
                'success': False,
                'error': 'akshare 或 pandas 模块不可用',
                'data': None
            }
        except Exception as e:
            self.logger.error(f"质量筛选失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }


# 全局实例
financial_analysis_service = FinancialAnalysisService()
