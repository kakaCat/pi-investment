"""
策略数据提供服务

负责K线数据获取、资金流数据、财务数据的注入和预处理
"""

import structlog
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, date

from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
from application.services.sentiment_service import SentimentService

logger = structlog.get_logger(__name__)


class StrategyDataProvider:
    """策略数据提供服务"""

    def __init__(self):
        self.kline_repo = KlineORMRepository()
        fund_flow_source = FundFlowDataSource()
        self.sentiment_service = SentimentService(fund_flow_source)

    def get_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        period: Optional[str] = None
    ) -> List[Dict]:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 数量限制（可选）
            period: K线周期（None=日线, '5min'/'15min'/'30min'/'60min'=分钟线）

        Returns:
            K线数据列表
        """
        try:
            if period and period in ('1min', '5min', '15min', '30min', '60min'):
                # 分钟K线
                if start_date and end_date:
                    start_ts = f"{start_date} 00:00:00" if ' ' not in str(start_date) else start_date
                    end_ts = f"{end_date} 23:59:59" if ' ' not in str(end_date) else end_date
                    klines = self.kline_repo.get_minute_klines(
                        symbol=symbol,
                        start_time=start_ts,
                        end_time=end_ts
                    )
                elif limit:
                    klines = self.kline_repo.get_latest_minute_klines(symbol=symbol, limit=limit)
                else:
                    raise ValueError("分钟K线必须指定 start_date/end_date 或 limit")

                # 归一化字段名：trade_datetime → trade_date
                for k in klines:
                    if 'trade_datetime' in k:
                        k['trade_date'] = str(k['trade_datetime'])

                # 聚合到目标周期
                if period in ('5min', '15min', '30min', '60min') and klines:
                    klines = self.aggregate_minute_klines(klines, period)

                logger.info(f"获取分钟K线 ({period}): {symbol}, {len(klines)} bars")
                return klines
            else:
                # 日K线
                if start_date and end_date:
                    return self.kline_repo.get_range(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date
                    )
                elif limit:
                    return self.kline_repo.get_latest(
                        symbol=symbol,
                        limit=limit
                    )
                else:
                    raise ValueError("必须指定 start_date/end_date 或 limit")
        except Exception as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            raise

    def aggregate_minute_klines(
        self,
        klines: List[Dict],
        target_period: str
    ) -> List[Dict]:
        """
        从分钟K线聚合到目标周期

        Args:
            klines: 分钟K线列表（按trade_datetime升序）
            target_period: 目标周期 '5min' / '15min' / '30min' / '60min'

        Returns:
            聚合后的K线列表
        """
        # klines is a Polars DataFrame, check if empty using .is_empty()
        if klines.is_empty():
            return []

        # Convert to pandas for aggregation
        import pandas as pd
        df = klines.to_pandas()

        # 周期映射（分钟数）
        period_minutes = {
            '5min': 5,
            '15min': 15,
            '30min': 30,
            '60min': 60
        }

        minutes = period_minutes.get(target_period)
        if not minutes:
            raise ValueError(f"不支持的周期: {target_period}")

        df['trade_datetime'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_datetime')

        # 按周期分组聚合
        df['period_group'] = df['trade_datetime'].dt.floor(f'{minutes}min')

        aggregated = df.groupby('period_group').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }).reset_index()

        aggregated['trade_date'] = aggregated['period_group'].dt.strftime('%Y-%m-%d %H:%M:%S')
        aggregated = aggregated.drop(columns=['period_group'])

        logger.info(f"聚合K线: {len(klines)} bars → {len(aggregated)} bars ({target_period})")

        return aggregated.to_dict('records')

    def inject_fund_flow(
        self,
        klines: List[Dict],
        symbol: str
    ) -> List[Dict]:
        """
        注入主力资金流向数据

        Returns:
            增强后的K线数据（包含资金流列）
        """
        # 字段名映射
        COLUMN_MAP = {
            '主力净流入-净额': 'main_net_inflow',
            '主力净流入-净占比': 'main_net_pct',
            '超大单净流入-净额': 'super_large_net',
            '超大单净流入-净占比': 'super_large_pct',
            '大单净流入-净额': 'large_net',
            '大单净流入-净占比': 'large_pct',
        }

        # 初始化所有资金流列为 NaN
        for k in klines:
            for eng_col in COLUMN_MAP.values():
                k[eng_col] = float('nan')

        logger.debug(f"资金流列初始化完成: {symbol}, klines数量={len(klines)}")

        try:
            # 获取资金流数据
            days = max(len(klines), 30)
            if klines:
                first_date_str = str(klines[0].get('trade_date', klines[0].get('date', ''))).strip()
                first_date_clean = first_date_str.replace('-', '')[:8]
                if len(first_date_clean) == 8:
                    try:
                        first_dt = date(
                            int(first_date_clean[:4]),
                            int(first_date_clean[4:6]),
                            int(first_date_clean[6:8])
                        )
                        days = max((date.today() - first_dt).days + 30, len(klines), 30)
                    except ValueError:
                        pass

            fund_data = self.sentiment_service.get_stock_fund_flow(symbol, days=days)

            if 'error' in fund_data or not fund_data.get('data'):
                logger.debug(f"资金流数据不可用: {symbol} - {fund_data.get('error', 'no data')}")
                return klines

            # 建立日期→资金流映射
            fund_by_date = {}
            for record in fund_data['data']:
                date_str = record.get('日期', '')
                if not date_str:
                    continue
                # 统一日期格式为 YYYY-MM-DD
                normalized_date = str(date_str).strip().replace('-', '')[:8]
                if len(normalized_date) == 8:
                    normalized_date = f"{normalized_date[:4]}-{normalized_date[4:6]}-{normalized_date[6:8]}"
                fund_by_date[normalized_date] = record

            # 匹配kline日期与资金流日期
            matched = 0
            for k in klines:
                kline_date = str(k.get('trade_date', k.get('date', ''))).strip()
                # 统一格式为 YYYY-MM-DD
                normalized_kline_date = kline_date.replace('-', '').split(' ')[0][:8]
                if len(normalized_kline_date) == 8:
                    normalized_kline_date = f"{normalized_kline_date[:4]}-{normalized_kline_date[4:6]}-{normalized_kline_date[6:8]}"

                if normalized_kline_date in fund_by_date:
                    fund = fund_by_date[normalized_kline_date]
                    for cn_col, eng_col in COLUMN_MAP.items():
                        val = fund.get(cn_col)
                        if val is not None:
                            try:
                                k[eng_col] = float(val)
                            except (ValueError, TypeError):
                                k[eng_col] = float('nan')
                    matched += 1

            logger.info(f"资金流数据注入完成: {symbol}, 匹配 {matched}/{len(klines)} 条")

        except Exception as e:
            logger.warning(f"注入资金流数据失败: {symbol}, 错误: {e}")

        return klines

    def inject_financial(
        self,
        klines: List[Dict],
        symbol: str
    ) -> List[Dict]:
        """
        注入财务指标数据

        Returns:
            增强后的K线数据（包含财务指标列）
        """
        # 初始化财务列为 NaN
        FINANCIAL_COLUMNS = [
            'roe_q', 'gross_margin_q', 'debt_ratio_q',
            'current_ratio_q', 'quick_ratio_q', 'net_profit_growth_q',
            'revenue_growth_q', 'operating_cashflow_q'
        ]

        for k in klines:
            for col in FINANCIAL_COLUMNS:
                k[col] = float('nan')

        logger.debug(f"财务列初始化完成: {symbol}, klines数量={len(klines)}")

        try:
            # TODO: 实现财务数据获取和匹配逻辑
            # 这里需要调用 FinancialDataService 获取季度财务数据
            # 然后根据 kline 日期匹配最近的季度数据
            logger.debug(f"财务数据注入: {symbol} (占位实现)")

        except Exception as e:
            logger.warning(f"注入财务数据失败: {symbol}, 错误: {e}")

        return klines

    def inject_market_filter(
        self,
        klines: List[Dict],
        bear_filter_enabled: bool = True
    ) -> List[Dict]:
        """
        注入市场过滤器数据（沪深300指数MA200）

        Returns:
            增强后的K线数据（包含市场过滤器列）
        """
        # 初始化市场过滤器列
        for k in klines:
            k['csi300_close'] = float('nan')
            k['csi300_ma200'] = float('nan')
            k['market_bear'] = False

        if not bear_filter_enabled:
            logger.debug("市场过滤器已禁用")
            return klines

        try:
            # TODO: 实现市场过滤器逻辑
            # 获取沪深300指数数据
            # 计算MA200
            # 判断熊市状态
            logger.debug("市场过滤器注入 (占位实现)")

        except Exception as e:
            logger.warning(f"注入市场过滤器失败: {e}")

        return klines

    def normalize_date(self, date_input) -> str:
        """
        归一化日期格式为 YYYY-MM-DD

        Args:
            date_input: 日期对象、字符串或时间戳

        Returns:
            YYYY-MM-DD 格式的日期字符串
        """
        if isinstance(date_input, str):
            # 移除时间部分
            return date_input.split(' ')[0].replace('-', '')[:8]
        elif isinstance(date_input, (datetime, date)):
            return date_input.strftime('%Y-%m-%d')
        else:
            return str(date_input)
