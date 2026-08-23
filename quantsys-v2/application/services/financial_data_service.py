"""
财务数据服务 - 多数据源协调器

提供多数据源 fallback 机制，依次尝试各个数据源直到成功，最终 fallback 到数据库。
类似 RealtimeQuoteService 的架构。
"""
from domain.ports import IFinancialRepository, IKlineRepository
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = structlog.get_logger(__name__)


class FinancialDataService:
    """财务数据服务

    多数据源协调器，按优先级依次尝试各个数据源，最终 fallback 到数据库。

    Attributes:
        providers: 数据源列表（按优先级排序）
        total_requests: 总请求数
        success_count: 成功次数
        failure_count: 失败次数
        provider_stats: 各数据源统计信息
    """

    def __init__(self, providers: Optional[List] = None, financial_repo=None, kline_repo=None):
        """初始化服务

        Args:
            providers: 可选的数据源列表。如果为 None，使用默认顺序：
                      eastmoney_direct → sina_web → akshare → sina
            financial_repo: 财务数据仓储（用于数据库 fallback）
            kline_repo: K线数据仓储（用于估值计算）
        """
        if providers is None:
            # 默认数据源优先级：API优先 → 网页爬虫兜底 → akshare备选
            # (2026-06: 腾讯 fqkline API 已变更返回 "bad params"，移除)
            from application.services.financial_providers import (
                EastmoneyDirectProvider,
                SinaWebFinancialProvider,
                AkshareFinancialProvider,
                SinaFinancialProvider,
            )

            provider_classes = [
                EastmoneyDirectProvider,    # 1. 东方财富直接API（最快，已验证可用）
                SinaWebFinancialProvider,   # 2. 新浪财经网页爬虫（独立，无需akshare）
                AkshareFinancialProvider,   # 3. AkShare（需akshare库，底层也连东方财富）
                SinaFinancialProvider,      # 4. 新浪财经 via AkShare
            ]

            self.providers = []
            for pc in provider_classes:
                try:
                    self.providers.append(pc())
                except Exception as e:
                    logger.warning(f"Failed to initialize {pc.__name__}: {e}")
        else:
            self.providers = providers

        # 注入的仓储
        self._financial_repo = financial_repo
        self._kline_repo = kline_repo

        # 统计信息
        self.total_requests = 0
        self.success_count = 0
        self.failure_count = 0
        self.provider_stats: Dict[str, Dict[str, int]] = {}

        # 初始化各 provider 的统计
        for provider in self.providers:
            self.provider_stats[provider.name] = {
                'success': 0,
                'failure': 0,
            }

        logger.info(
            f"FinancialDataService initialized with {len(self.providers)} providers: "
            f"{[p.name for p in self.providers]}"
        )

    def get_financial_data(self, symbol: str, statement_type: str = 'all', periods: int = 4):
        """获取财务数据（兼容 provider 接口）

        依次尝试各个数据源。

        Args:
            symbol: 股票代码
            statement_type: 报表类型
            periods: 期数

        Returns:
            FinancialStatementData 对象，失败时抛出异常
        """
        self.total_requests += 1
        logger.info(f"Fetching financial data for {symbol}, trying {len(self.providers)} providers")

        # 尝试各个外部数据源
        for i, provider in enumerate(self.providers, 1):
            try:
                logger.debug(f"Trying provider {i}/{len(self.providers)}: {provider.name}")

                # 获取财务报表数据
                financial_data = provider.get_financial_data(
                    symbol=symbol,
                    statement_type=statement_type,
                    periods=periods
                )

                if financial_data and (financial_data.income_statement or financial_data.balance_sheet):
                    logger.info(f"Successfully fetched financial data for {symbol} from {provider.name}")
                    self.success_count += 1
                    self.provider_stats[provider.name]['success'] += 1
                    return financial_data

                # provider 返回空数据
                logger.warning(f"Provider {provider.name} returned no data for {symbol}")
                self.provider_stats[provider.name]['failure'] += 1

            except Exception as e:
                # provider 抛出异常
                logger.warning(
                    f"Provider {provider.name} failed for {symbol}: {type(e).__name__}: {e}"
                )
                self.provider_stats[provider.name]['failure'] += 1

        # 所有数据源失败
        logger.error(f"All providers failed for {symbol}")
        self.failure_count += 1
        raise Exception(f"All providers failed for {symbol}")

    def get_financial_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取财务指标

        依次尝试各个数据源，最终 fallback 到数据库。

        Args:
            symbol: 股票代码

        Returns:
            财务指标字典 或 None（所有数据源都失败时）
        """
        self.total_requests += 1
        logger.info(f"Fetching financial indicators for {symbol}, trying {len(self.providers)} providers")

        # 尝试各个外部数据源
        for i, provider in enumerate(self.providers, 1):
            try:
                logger.debug(f"Trying provider {i}/{len(self.providers)}: {provider.name}")

                # 获取财务报表数据（20期 = 5年季报）
                financial_data = provider.get_financial_data(
                    symbol=symbol,
                    statement_type='all',
                    periods=20
                )

                if financial_data and (financial_data.income_statement or financial_data.balance_sheet):
                    # 从报表中提取关键指标
                    indicators = self._extract_indicators(financial_data)

                    if indicators:
                        logger.info(
                            f"Successfully fetched financial indicators for {symbol} from {provider.name}"
                        )
                        self.success_count += 1
                        self.provider_stats[provider.name]['success'] += 1
                        return {
                            'success': True,
                            'data': {
                                'symbol': symbol,
                                'source': provider.name,
                                'indicators': indicators,
                                'update_time': datetime.now().isoformat()
                            }
                        }

                # provider 返回空数据
                logger.warning(f"Provider {provider.name} returned no data for {symbol}")
                self.provider_stats[provider.name]['failure'] += 1

            except Exception as e:
                # provider 抛出异常
                logger.warning(
                    f"Provider {provider.name} failed for {symbol}: {type(e).__name__}: {e}"
                )
                self.provider_stats[provider.name]['failure'] += 1

        # 所有外部数据源失败，fallback 到数据库
        logger.info(f"All external providers failed for {symbol}, trying database")
        db_result = self._get_from_database(symbol)
        if db_result:
            self.success_count += 1
            return db_result

        # 所有数据源（包括数据库）都失败
        logger.error(f"All providers (including database) failed for {symbol}")
        self.failure_count += 1
        return None

    def get_valuation(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取估值数据

        尝试从数据库计算估值指标，如果失败则返回 None。

        Args:
            symbol: 股票代码

        Returns:
            估值数据字典 或 None
        """
        self.total_requests += 1
        logger.info(f"Fetching valuation for {symbol}")

        try:
            # 获取仓储实例
            if self._financial_repo is None or self._kline_repo is None:
                from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                from domain.ports import IFinancialRepository, IKlineRepository
                financial_repo = self._financial_repo or EnhancedServiceFactory.resolve(IFinancialRepository)
                kline_repo = self._kline_repo or EnhancedServiceFactory.resolve(IKlineRepository)
            else:
                financial_repo = self._financial_repo
                kline_repo = self._kline_repo

            # 获取最新股价
            latest_kline = kline_repo.get_latest_kline(symbol)
            if not latest_kline:
                logger.warning(f"No kline data found for {symbol}")
                return None

            current_price = latest_kline.get('close')

            # 获取最新财务数据
            income_data = financial_repo.get_income_statements(symbol, period_type='Y', limit=1)
            balance_data = financial_repo.get_balance_sheets(symbol, period_type='Y', limit=1)

            if not income_data or not balance_data:
                logger.warning(f"No financial data found in database for {symbol}")
                return None

            income = income_data[0]
            balance = balance_data[0]

            # 计算 PE (市盈率 = 股价 / 每股收益)
            net_profit = income.get('net_profit') or income.get('归属母公司所有者的净利润')
            total_shares = balance.get('total_share_capital') or balance.get('股本')

            pe_ratio = None
            if net_profit and total_shares and current_price:
                eps = net_profit / total_shares  # 每股收益
                if eps > 0:
                    pe_ratio = current_price / eps

            # 计算 PB (市净率 = 股价 / 每股净资产)
            net_assets = balance.get('total_equity') or balance.get('股东权益合计')
            pb_ratio = None
            if net_assets and total_shares and current_price:
                bps = net_assets / total_shares  # 每股净资产
                if bps > 0:
                    pb_ratio = current_price / bps

            if pe_ratio or pb_ratio:
                self.success_count += 1
                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'valuation': {
                            'pe': round(pe_ratio, 2) if pe_ratio else None,
                            'pb': round(pb_ratio, 2) if pb_ratio else None,
                            'current_price': current_price,
                            'calculation_date': income.get('report_date') or income.get('报告期')
                        },
                        'source': 'database_calculated',
                        'update_time': datetime.now().isoformat()
                    }
                }

        except Exception as e:
            logger.error(f"Failed to calculate valuation for {symbol}: {e}", exc_info=True)

        self.failure_count += 1
        return None

    def _extract_indicators(self, financial_data) -> Optional[List[Dict[str, Any]]]:
        """从财务报表中提取关键指标

        Args:
            financial_data: FinancialData 对象

        Returns:
            指标列表
        """
        indicators = []

        # 从利润表提取
        if financial_data.income_statement:
            for period in financial_data.income_statement[:3]:  # 最近3期
                indicator = {
                    'report_date': period.get('报告日') or period.get('report_date'),
                    'revenue': period.get('营业总收入') or period.get('revenue'),
                    'net_profit': period.get('净利润') or period.get('net_profit'),
                    'gross_margin': period.get('销售毛利率') or period.get('gross_margin'),
                }
                indicators.append(indicator)

        return indicators if indicators else None

    def _is_valid_financial_data(self, data) -> bool:
        """验证财务数据是否有效

        Args:
            data: FinancialStatementData 对象

        Returns:
            True if data is valid, False otherwise
        """
        if not data:
            return False

        # 检查是否有任何报表数据
        has_data = bool(
            data.income_statement or
            data.balance_sheet or
            data.cash_flow
        )

        return has_data

    def _get_from_database(self, symbol: str) -> Optional[Dict[str, Any]]:
        """从数据库获取财务指标

        Args:
            symbol: 股票代码

        Returns:
            财务指标字典 或 None
        """
        try:
            # 获取仓储实例
            if self._financial_repo is None:
                from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                from domain.ports import IFinancialRepository
                financial_repo = EnhancedServiceFactory.resolve(IFinancialRepository)
            else:
                financial_repo = self._financial_repo

            # 获取最近的利润表和资产负债表
            income_data = financial_repo.get_income_statements(symbol, period_type='Y', limit=5)
            balance_data = financial_repo.get_balance_sheets(symbol, period_type='Y', limit=5)

            if income_data and balance_data:
                logger.info(f"Successfully fetched financial data from database for {symbol}")
                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'source': 'database',
                        'income_statements': income_data[:3],  # 最近3年
                        'balance_sheets': balance_data[:3],
                        'total': len(income_data),
                        'update_time': datetime.now().isoformat()
                    }
                }
        except Exception as e:
            logger.warning(f"Database query failed for {symbol}: {e}")

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        return {
            'total_requests': self.total_requests,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': (
                self.success_count / self.total_requests
                if self.total_requests > 0 else 0
            ),
            'provider_stats': self.provider_stats,
        }
