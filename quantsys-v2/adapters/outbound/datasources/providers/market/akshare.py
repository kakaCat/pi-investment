"""Akshare market data provider."""
import logging
from typing import Optional
from datetime import datetime
from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)


class AkshareMarketProvider(MarketProvider):
    """Akshare market data provider"""

    @property
    def name(self) -> str:
        return 'akshare'

    def get_market_overview(self) -> Optional[MarketData]:
        """Get market overview (rise/fall counts, indices)

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # Get market overview data
            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                logger.warning(f"{self.name}: No market overview data")
                return None

            # Calculate rise/fall counts
            rise_count = len(df[df['涨跌幅'] > 0])
            fall_count = len(df[df['涨跌幅'] < 0])
            unchanged_count = len(df[df['涨跌幅'] == 0])

            overview_data = {
                'rise': rise_count,
                'fall': fall_count,
                'unchanged': unchanged_count,
                'total': len(df)
            }

            return MarketData(
                data_type='overview',
                data=overview_data,
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_market_overview failed: {e}")
            return None

    def get_market_spot(self) -> Optional[MarketData]:
        """获取全市场快照（stock_zh_a_spot_em 原始记录列表）

        供估值/筛选等需要 PE/PB/市值字段的场景使用（Phase 3 数据访问治理：
        集中 akshare 调用到数据源层）。

        Returns:
            MarketData(data=list of raw record dicts) or None if failed
        """
        try:
            import akshare as ak

            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                logger.warning(f"{self.name}: No market spot data")
                return None

            # NaN → None，保证 JSON 可序列化
            records = df.where(df.notna(), None).to_dict('records')

            return MarketData(
                data_type='market_spot',
                data={'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_market_spot failed: {e}")
            return None

    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        """Get dragon-tiger list (龙虎榜) for a stock

        Args:
            symbol: Stock symbol
            date: Date (YYYY-MM-DD)

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # stock_lhb_detail_em 真实签名为 (start_date, end_date)，无 symbol 参数
            # （2026-08-19 修复：原先传 symbol=symbol 是 latent bug，调用必 TypeError）
            # 拉取全量后按 symbol 过滤（代码列名为"代码"，可能是 6 位裸码或带后缀）
            df = ak.stock_lhb_detail_em(start_date=date.replace('-', ''), end_date=date.replace('-', ''))

            if df is None or df.empty:
                logger.warning(f"{self.name}: No LHB data on {date}")
                return None

            bare = symbol.split('.')[0]
            code_col = '代码' if '代码' in df.columns else None
            if code_col:
                df = df[df[code_col].astype(str).str.contains(bare)]

            if df.empty:
                logger.warning(f"{self.name}: No LHB data for {symbol} on {date}")
                return None

            lhb_data = df.to_dict('records')

            return MarketData(
                data_type='lhb',
                data={'symbol': symbol, 'date': date, 'records': lhb_data},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_stock failed: {e}")
            return None

    def get_lhb_detail(self, symbol: str, start_date: str, end_date: str) -> Optional[MarketData]:
        """获取指定股票在日期区间内的龙虎榜明细

        Args:
            symbol: Stock symbol (600519 或 600519.SH)
            start_date: 开始日期（YYYY-MM-DD 或 YYYYMMDD）
            end_date: 结束日期（YYYY-MM-DD 或 YYYYMMDD）

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            df = ak.stock_lhb_detail_em(
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', '')
            )

            if df is None or df.empty:
                return None

            bare = symbol.split('.')[0]
            code_col = '代码' if '代码' in df.columns else None
            if code_col:
                df = df[df[code_col].astype(str).str.contains(bare)]

            if df.empty:
                return None

            records = df.to_dict('records')
            return MarketData(
                data_type='lhb_detail',
                data={'symbol': symbol, 'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_detail failed: {e}")
            return None

    def get_zt_pool(self, date: str) -> Optional[MarketData]:
        """获取涨停池（stock_zt_pool_em）

        Args:
            date: 日期（YYYY-MM-DD 或 YYYYMMDD）

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            df = ak.stock_zt_pool_em(date=date.replace('-', ''))

            if df is None or df.empty:
                return None

            records = df.to_dict('records')
            return MarketData(
                data_type='zt_pool',
                data={'date': date, 'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_zt_pool failed: {e}")
            return None

    def get_market_margin(self) -> Optional[MarketData]:
        """全市场融资融券余额（上交所历史 + 深交所当日，两源独立容错）

        Returns:
            MarketData(data={'sh': [...], 'sz': [...]})，两源均失败返回 None
        """
        try:
            import akshare as ak
            import pandas as pd

            try:
                df_sh = ak.stock_margin_sse()
            except Exception as e:
                logger.warning(f"{self.name} 上交所两融获取失败: {e}")
                df_sh = pd.DataFrame()

            try:
                today = datetime.now().strftime("%Y%m%d")
                df_sz = ak.stock_margin_szse(date=today)
            except Exception as e:
                logger.warning(f"{self.name} 深交所两融获取失败: {e}")
                df_sz = pd.DataFrame()

            if df_sh.empty and df_sz.empty:
                return None

            return MarketData(
                data_type='market_margin',
                data={
                    'sh': df_sh.tail(30).to_dict('records') if not df_sh.empty else [],
                    'sz': df_sz.to_dict('records') if not df_sz.empty else [],
                },
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_market_margin failed: {e}")
            return None

    def get_sector_fund_flow(self, indicator: str = '今日') -> Optional[MarketData]:
        """行业资金流向排行（stock_sector_fund_flow_rank）

        Args:
            indicator: '今日' | '5日' | '10日'

        Returns:
            MarketData(data={'records': [...]}) or None if failed
        """
        try:
            from infrastructure.config.proxy import proxy_disabled
            import akshare as ak

            # 禁用代理（与 kline provider 一致：避免代理导致连接失败）
            with proxy_disabled():
                df = ak.stock_sector_fund_flow_rank(indicator=indicator)

            if df is None or df.empty:
                return None

            records = df.where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='sector_fund_flow',
                data={'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_sector_fund_flow failed: {e}")
            return None

    def get_macro_data(self) -> Optional[MarketData]:
        """宏观经济数据（GDP/CPI/PMI 最新值）

        Returns:
            MarketData(data={'gdp': [...], 'cpi': [...], 'pmi': [...]}) or None if failed
        """
        try:
            import akshare as ak

            gdp_df = ak.macro_china_gdp()
            cpi_df = ak.macro_china_cpi_yearly()
            pmi_df = ak.macro_china_pmi_yearly()

            return MarketData(
                data_type='macro',
                data={
                    # GDP 倒序（最新在前）用 head；CPI/PMI 正序用 tail
                    'gdp': gdp_df.head(5).to_dict('records') if gdp_df is not None and not gdp_df.empty else [],
                    'cpi': cpi_df.tail(5).to_dict('records') if cpi_df is not None and not cpi_df.empty else [],
                    'pmi': pmi_df.tail(5).to_dict('records') if pmi_df is not None and not pmi_df.empty else [],
                },
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_macro_data failed: {e}")
            return None

    def get_market_news(self) -> Optional[MarketData]:
        """全市场财经新闻（stock_news_em 无参版，与 stock provider 的个股新闻不同）

        Returns:
            MarketData(data={'records': [...]}) or None if failed
        """
        try:
            import akshare as ak

            df = ak.stock_news_em()

            if df is None or df.empty:
                return None

            records = df.where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='market_news',
                data={'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_market_news failed: {e}")
            return None

    def get_index_daily(self, symbol: str) -> Optional[MarketData]:
        """指数历史日K（stock_zh_index_daily，如 sh000300）

        Returns:
            MarketData(data={'records': [...]})，date 列已归一为字符串
        """
        try:
            import akshare as ak

            df = ak.stock_zh_index_daily(symbol=symbol)

            if df is None or df.empty:
                return None

            df = df.copy()
            df['date'] = df['date'].astype(str)
            records = df.where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='index_daily',
                data={'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_index_daily failed: {e}")
            return None

    def get_insider_trades(self, symbol: str) -> Optional[MarketData]:
        """股东增减持数据（stock_dzjy_hygtj，作为内幕交易的替代指标）

        Args:
            symbol: 股票代码（akshare 需要 6 位裸码）

        Returns:
            MarketData(data={'records': [...]}) or None if failed
        """
        try:
            import akshare as ak

            df = ak.stock_dzjy_hygtj(symbol=symbol.split('.')[0])

            if df is None or df.empty:
                return None

            records = df.where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='insider_trades',
                data={'symbol': symbol, 'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_insider_trades failed: {e}")
            return None

    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        """Get daily dragon-tiger list

        Args:
            date: Date (YYYY-MM-DD)

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # Get daily LHB data
            df = ak.stock_lhb_stock_statistic_em(start_date=date, end_date=date)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No daily LHB data for {date}")
                return None

            lhb_data = df.to_dict('records')

            return MarketData(
                data_type='lhb_daily',
                data={'date': date, 'records': lhb_data, 'total': len(lhb_data)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_daily failed: {e}")
            return None
