"""Akshare market data provider."""
import logging
import threading
import time as _time
from typing import Optional
from datetime import datetime, timedelta
from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)

# ── 龙虎榜全市场数据缓存（2026-09-11，w-f4aa1f6a） ──────────────────────────
# ak.stock_lhb_detail_em 是「全市场 + 日期区间」接口，get_lhb_detail(symbol,..)
# 只是本地按代码过滤。此前 ManipulationDetector 对每只涨停股各调一次
# → 20 只票 = 20 次同参数 HTTP（cProfile 实测 10.4s，占 /api/alerts/check 全部耗时 11.5s）。
# 龙虎榜按日发布、当日收盘后不再变化，按 (start,end) 做 10 分钟 TTL 缓存即可。
_LHB_CACHE: dict = {}
_LHB_CACHE_TTL_SECONDS = 600.0
_LHB_CACHE_MAX_ENTRIES = 8
_LHB_CACHE_LOCK = threading.Lock()


def _fetch_lhb_market_df(start_date: str, end_date: str):
    """获取并缓存全市场龙虎榜 DataFrame（失败/空返回 None，不缓存空结果）。"""
    key = (start_date, end_date)
    now = _time.monotonic()
    with _LHB_CACHE_LOCK:
        hit = _LHB_CACHE.get(key)
        if hit and now - hit[0] < _LHB_CACHE_TTL_SECONDS:
            return hit[1]

    import akshare as ak

    df = ak.stock_lhb_detail_em(
        start_date=start_date.replace('-', ''),
        end_date=end_date.replace('-', '')
    )
    if df is None or df.empty:
        return None

    with _LHB_CACHE_LOCK:
        if len(_LHB_CACHE) >= _LHB_CACHE_MAX_ENTRIES:
            oldest = min(_LHB_CACHE.items(), key=lambda kv: kv[1][0])[0]
            _LHB_CACHE.pop(oldest, None)
        _LHB_CACHE[key] = (now, df)
    return df


# ── 股东 / 基金 / 千股千评 全市场 DataFrame 缓存（2026-09-14，REQ-48d896） ────
# stock_inner_trade_xq(2.5万行) / stock_comment_em(5196行) / stock_report_fund_hold(5225行)
# 都是「全市场」接口，单股调用只是本地过滤；不缓存则每个请求都打一次上游。
_SENTIMENT_CACHE: dict = {}
_SENTIMENT_CACHE_LOCK = threading.Lock()
_SENTIMENT_CACHE_TTLS = {
    'inner_trades': 300.0,    # 内部人交易按日更新
    'stock_comment': 600.0,   # 千股千评盘中会变
    'fund_hold': 1800.0,      # 基金持仓按季度披露
}


def _cached_market_df(name: str, loader):
    """按 name 做 TTL 缓存的全市场 DataFrame 获取；失败/空**不写入**缓存（下次重试）。"""
    ttl = _SENTIMENT_CACHE_TTLS.get(name, 600.0)
    now = _time.monotonic()
    with _SENTIMENT_CACHE_LOCK:
        hit = _SENTIMENT_CACHE.get(name)
        if hit and now - hit[0] < ttl:
            return hit[1]
    df = loader()
    if df is None or df.empty:
        return None
    with _SENTIMENT_CACHE_LOCK:
        _SENTIMENT_CACHE[name] = (now, df)
    return df


# 传输类异常（真故障）vs 数据/解析类异常（该期间无数据）必须区分：
# akshare 在「报告期无数据」时抛的是解析异常（ValueError/KeyError），不是网络异常。
# 把「无数据」当故障会让熔断器误伤健康源；把「网络挂」当无数据就是假成功。
_TRANSPORT_ERROR_TYPES = (ConnectionError, TimeoutError)


def _is_transport_error(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSPORT_ERROR_TYPES):
        return True
    mod = type(exc).__module__ or ''
    return mod.startswith(('requests', 'urllib3', 'http', 'socket', 'ssl'))


def _recent_report_periods(count: int = 4) -> list:
    """最近 count 个候选财报报告期（YYYYMMDD，新→旧）。

    披露有滞后（年报次年 4/30 前、季报次月底前），故这里只给候选序列，
    由调用方按序回退取到数据为止 —— 不猜「哪个已披露」。
    """
    today = datetime.now().date()
    cands = []
    for y in (today.year, today.year - 1, today.year - 2):
        for md in ('1231', '0930', '0630', '0331'):
            d = datetime(int(y), int(md[:2]), int(md[2:])).date()
            if d <= today:
                cands.append(d)
    return [d.strftime('%Y%m%d') for d in sorted(set(cands), reverse=True)[:count]]


def _em_prefixed_lower(symbol: str) -> str:
    """600519 → sh600519（东财小写前缀）。

    复用 industry_chain 已有的 market_prefixed（全仓前缀规则唯一实现），
    本处只做大小写转换 —— 不重写一份前缀规则。
    """
    from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
        market_prefixed,
    )
    return market_prefixed(symbol).lower()


def _df_records(df) -> list:
    """DataFrame → JSON 安全 records。

    日期/时间列必须转成字符串：`datetime.date` 不是 JSON 可序列化类型，
    直接塞进响应会让路由在编码阶段 500（get_index_daily 早已在其内部 stringify，
    这里是同一个坑的通用解法）。
    """
    records = df.astype(object).where(df.notna(), None).to_dict('records')
    for rec in records:
        for key, val in rec.items():
            if hasattr(val, 'isoformat'):
                rec[key] = val.isoformat()
    return records


def _normalize_quarter(quarter) -> Optional[str]:
    """'2024Q4' / '20241231' / '2024-12-31' → 'YYYY-MM-DD'；无法解析返回 None。"""
    if not quarter:
        return None
    q = str(quarter).strip().upper().replace('-', '')
    qmap = {'Q1': '0331', 'Q2': '0630', 'Q3': '0930', 'Q4': '1231'}
    if q.endswith(tuple(qmap)):  # 2024Q4
        year, qn = q[:4], q[-2:]
        if year.isdigit() and qn in qmap:
            q = year + qmap[qn]
    if len(q) == 8 and q.isdigit():
        return '%s-%s-%s' % (q[:4], q[4:6], q[6:])
    return None


class AkshareMarketProvider(MarketProvider):
    """Akshare market data provider"""

    @property
    def name(self) -> str:
        return 'akshare'

    def get_market_overview(self) -> Optional[MarketData]:
        """Get market overview (rise/fall counts, indices)

        2026-09-05: 主源改乐咕乐股 stock_market_activity_legu——原主源
        stock_zh_a_spot_em 依赖 82.push2.eastmoney.com，该域在当前网络
        (系统代理 GeoIP(cn)→DIRECT 直连,IPv6 TLS 被断)必失败且重试耗 5-6s；
        legu 走 legulegu.com 独立域，实测 0.1s 可用。spot_em 保留为兜底
        (网络恢复后自动回退)。两者均输出 {rise, fall, unchanged, total}。

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # --- 主源：乐咕乐股 市场活跃度（item/value 两列） ---
            # 字段: 上涨/涨停/下跌/跌停/平盘/停牌/活跃度/统计日期
            try:
                df = ak.stock_market_activity_legu()
                if df is not None and not df.empty and {'item', 'value'} <= set(df.columns):
                    kv = dict(zip(df['item'].astype(str), df['value']))
                    try:
                        rise = int(float(kv.get('上涨', 0)))
                        fall = int(float(kv.get('下跌', 0)))
                        unchanged = int(float(kv.get('平盘', 0)))
                        suspended = int(float(kv.get('停牌', 0)))
                        overview_data = {
                            'rise': rise,
                            'fall': fall,
                            'unchanged': unchanged,
                            # total 含停牌，接近全市场股票口径
                            'total': rise + fall + unchanged + suspended,
                        }
                        return MarketData(
                            data_type='overview',
                            data=overview_data,
                            source=f'{self.name}_legu',
                            timestamp=datetime.now().isoformat()
                        )
                    except (TypeError, ValueError) as e:
                        logger.warning(f"{self.name} get_market_overview legu parse failed: {e}")
                else:
                    logger.warning(f"{self.name} get_market_overview legu empty/format unexpected")
            except Exception as e:
                logger.warning(f"{self.name} get_market_overview legu failed: {e}, fallback to em spot")

            # --- 兜底：东财全市场快照（原主源；82.push2 网络恢复后可用） ---
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
            records = _df_records(df)

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

            lhb_data = df.astype(object).where(df.notna(), None).to_dict('records')

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

            # 空日期默认最近 30 天（避免空字符串传给 akshare 返回全量/报错）
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            # 走缓存：同一 (start,end) 的全市场龙虎榜只抓一次（见文件头缓存说明）
            df = _fetch_lhb_market_df(start_date, end_date)

            if df is None or df.empty:
                return None

            bare = symbol.split('.')[0]
            code_col = '代码' if '代码' in df.columns else None
            if code_col:
                df = df[df[code_col].astype(str).str.contains(bare)]

            if df.empty:
                return None

            records = _df_records(df)
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

            records = _df_records(df)
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
            import os
            from unittest.mock import patch
            import akshare as ak

            # 禁用代理（与 kline provider 一致：避免代理导致连接失败）
            env_patch = {'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'http_proxy': '', 'https_proxy': ''}
            with patch.dict(os.environ, env_patch, clear=False):
                df = ak.stock_sector_fund_flow_rank(indicator=indicator)

            if df is None or df.empty:
                return None

            records = _df_records(df)
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

            def _sanitize_records(records):
                # 2026-08-30 修复：akshare 返回的 DataFrame 可能含 NaN，
                # 序列化时报 ValueError: Out of range float values (nan)，统一清洗为 None
                cleaned = []
                for rec in records or []:
                    cleaned.append({k: (None if isinstance(v, float) and v != v else v) for k, v in rec.items()})
                return cleaned

            return MarketData(
                data_type='macro',
                data={
                    # GDP 倒序（最新在前）用 head；CPI/PMI 正序用 tail
                    'gdp': _sanitize_records(gdp_df.head(5).to_dict('records')) if gdp_df is not None and not gdp_df.empty else [],
                    'cpi': _sanitize_records(cpi_df.tail(5).to_dict('records')) if cpi_df is not None and not cpi_df.empty else [],
                    'pmi': _sanitize_records(pmi_df.tail(5).to_dict('records')) if pmi_df is not None and not pmi_df.empty else [],
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

            records = _df_records(df)
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
            records = _df_records(df)
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
        """内部人交易/高管增减持（stock_inner_trade_xq 全市场数据按代码筛选）

        Args:
            symbol: 股票代码（akshare 需要 6 位裸码）

        Returns:
            MarketData(data={'records': [...]}) or None if failed
        """
        try:
            import akshare as ak

            # 2026-09-01 修复：原实现 stock_dzjy_hygtj(symbol=代码) 是 latent bug——
            # 该接口 symbol 参数是周期（'近三月'），传股票代码必 KeyError。
            # 真正的内部人交易接口是 stock_inner_trade_xq()（全市场，按代码筛选）。
            # 2026-09-14（REQ-48d896）：加 5 分钟 TTL 缓存 —— 该接口返回全市场
            # 2.5 万行，单股调用只做本地过滤，不缓存等于每个请求都打一次上游。
            df = _cached_market_df('inner_trades', ak.stock_inner_trade_xq)

            if df is None or df.empty:
                return None

            bare = symbol.split('.')[0]
            code_col = '股票代码' if '股票代码' in df.columns else None
            if code_col:
                df = df[df[code_col].astype(str).str.replace('.', '').str.contains(bare, na=False)]

            if df.empty:
                # 无内部人交易记录是正常结果（非失败），返回空记录集
                return MarketData(
                    data_type='insider_trades',
                    data={'symbol': symbol, 'records': [], 'total': 0, 'empty': True},
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                )

            records = _df_records(df)
            return MarketData(
                data_type='insider_trades',
                data={'symbol': symbol, 'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_insider_trades failed: {e}")
            return None

    # ── 股东 / 基金 / 千股千评（2026-09-14，w-2129d492，REQ-48d896）──────────
    # 替换 adapters/outbound/datasources/sentiment_data_source.py 里 random 生成的
    # 伪造实现（该文件已删除）。契约与框架一致：
    #   · 硬失败（网络/传输）→ 返回 None → 计入熔断与 attempted_sources；
    #   · 健康空（源正常但该标的确实无数据）→ 返回 records=[] 的 MarketData
    #     → 计入 empty_sources，不误伤熔断；
    #   · 绝不返回无来源标记的数据。

    def get_top_holders(self, symbol: str, holder_type: str = 'top10') -> Optional[MarketData]:
        """十大股东（holder_type='top10'）或十大流通股东（'free'）。

        报告期不支持时 akshare 抛解析异常（属「该期无数据」，非传输故障）→
        回退到更早的报告期；四个候选期都取不到 → 健康空。
        """
        try:
            import akshare as ak

            prefixed = _em_prefixed_lower(symbol)
            if not prefixed:
                logger.warning(f"{self.name} get_top_holders: 无法识别市场前缀 symbol={symbol}")
                return None

            want_free = str(holder_type or '').lower() in ('free', 'circulating', 'free_float')
            fetcher = ak.stock_gdfx_free_top_10_em if want_free else ak.stock_gdfx_top_10_em
            kind = 'free' if want_free else 'top10'

            for period in _recent_report_periods(4):
                try:
                    df = fetcher(symbol=prefixed, date=period)
                except Exception as e:  # noqa: BLE001
                    if _is_transport_error(e):
                        logger.warning(f"{self.name} get_top_holders {symbol} 传输故障: {e}")
                        return None
                    continue  # 该报告期无数据，回退更早期间
                if df is None or df.empty:
                    continue
                records = _df_records(df)
                return MarketData(
                    data_type='top_holders',
                    data={
                        'symbol': symbol,
                        'holder_type': kind,
                        'report_date': '%s-%s-%s' % (period[:4], period[4:6], period[6:]),
                        'holders': records,
                        'total': len(records),
                    },
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                )

            return MarketData(
                data_type='top_holders',
                data={'symbol': symbol, 'holder_type': kind,
                      'report_date': None, 'holders': [], 'total': 0, 'empty': True},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"{self.name} get_top_holders failed: {e}")
            return None

    def get_holder_changes(self, symbol: str, periods: int = 4) -> Optional[MarketData]:
        """股东户数变化（东财 stock_zh_a_gdhs_detail_em），最新在前。"""
        try:
            import akshare as ak

            bare = str(symbol or '').split('.')[0]
            df = ak.stock_zh_a_gdhs_detail_em(symbol=bare)
            if df is None or df.empty:
                return MarketData(
                    data_type='holder_changes',
                    data={'symbol': symbol, 'periods': [], 'total': 0, 'empty': True},
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                )
            # 最新在前：上游返回的是升序（实测首行为 2013-03-22）
            date_cols = [c for c in df.columns if '截止日' in str(c) or '统计' in str(c)]
            if date_cols:
                df = df.sort_values(date_cols[0], ascending=False)
            n = max(1, int(periods or 4))
            df = df.head(n)
            records = _df_records(df)
            return MarketData(
                data_type='holder_changes',
                data={'symbol': symbol, 'periods': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"{self.name} get_holder_changes failed: {e}")
            return None

    def get_fund_holdings(self, symbol: str, quarter=None) -> Optional[MarketData]:
        """基金持股明细（东财 stock_fund_stock_holder）：哪些基金持有该股。

        quarter: '2024Q4' / '20241231' / '2024-12-31' / None（全部）；仅本地过滤。
        """
        try:
            import akshare as ak

            bare = str(symbol or '').split('.')[0]
            df = ak.stock_fund_stock_holder(symbol=bare)
            if df is None or df.empty:
                return MarketData(
                    data_type='fund_holdings',
                    data={'symbol': symbol, 'quarter': None, 'holdings': [], 'total': 0,
                          'empty': True},
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                )

            want = _normalize_quarter(quarter)
            applied = want
            if want:
                date_cols = [c for c in df.columns if '截止' in str(c) or '日期' in str(c)]
                if date_cols:
                    col = date_cols[0]
                    df = df[df[col].astype(str).str.replace('/', '-').str.startswith(want)]
                else:
                    # 没有日期列就无法按季度过滤 —— 如实置 None，不假装过滤成功
                    applied = None
                if df.empty:
                    return MarketData(
                        data_type='fund_holdings',
                        data={'symbol': symbol, 'quarter': applied, 'holdings': [], 'total': 0,
                              'empty': True},
                        source=self.name,
                        timestamp=datetime.now().isoformat(),
                    )

            records = _df_records(df)
            return MarketData(
                data_type='fund_holdings',
                data={'symbol': symbol, 'quarter': applied,
                      'holdings': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"{self.name} get_fund_holdings failed: {e}")
            return None

    def get_top_fund_stocks(self, fund_type: str = 'all', limit: int = 50) -> Optional[MarketData]:
        """机构重仓股排行（东财 stock_report_fund_hold）。

        返回列含「持有基金家数 / 持股总数 / 持股市值」—— 与旧契约
        fundCount / totalShares / totalValue 同义。
        """
        try:
            import akshare as ak

            type_map = {
                'all': '基金持仓', 'fund': '基金持仓', '基金': '基金持仓',
                'qfii': 'QFII持仓', 'social_security': '社保持仓', 'social': '社保持仓',
                'broker': '券商持仓', 'insurance': '保险持仓', 'trust': '信托持仓',
            }
            key = str(fund_type or 'all').lower()
            report_symbol = type_map.get(key) or type_map.get(str(fund_type)) or '基金持仓'

            df = None
            for period in _recent_report_periods(4):
                try:
                    cand = _cached_market_df(
                        'fund_hold:%s:%s' % (report_symbol, period),
                        lambda p=period: ak.stock_report_fund_hold(symbol=report_symbol, date=p),
                    )
                except Exception as e:  # noqa: BLE001
                    if _is_transport_error(e):
                        logger.warning(f"{self.name} get_top_fund_stocks 传输故障: {e}")
                        return None
                    continue
                if cand is not None and not cand.empty:
                    df = cand
                    break
            if df is None or df.empty:
                return MarketData(
                    data_type='top_fund_stocks',
                    data={'fund_type': report_symbol, 'report_date': None,
                          'stocks': [], 'total': 0, 'empty': True},
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                )

            # ── 上游完整性校验（2026-09-14，REQ-48d896）──────────────────────
            # ak.stock_report_fund_hold 当前返回**列名与值错位**的表：
            #   · 「股票代码」列是 1.4e11 这类浮点（实测 -42049165018.7）
            #   · 「股票简称」列装的才是 6 位代码（300308/600519）
            #   · 「持有基金家数」是 '01'、「持股变动比例」是 -20784953
            # 已试过换报告期（20241231/20250331/20260630 均错位）、换函数
            # （fund_report_stock_cninfo KeyError 'records'；fund_portfolio_hold_em
            # 是按基金的）——**没有可信替代源**。
            # 错位表绝不能当数据返回（这正是本需求要消灭的"假数据"，只是来源换成上游）。
            # 因此：检测到「股票代码列不是 6 位代码」即判定上游损坏 → 硬失败 None，
            # 让端点诚实报错；上游修好后本方法自动恢复。
            code_cols = [c for c in df.columns if str(c) in ('股票代码', '代码')]
            if code_cols:
                col = code_cols[0]
                codes = df[col].astype(str).str.replace(r'\.0$', '', regex=True)
                valid = codes.str.fullmatch(r'\d{6}')
                if not bool(valid.all()):
                    logger.error(
                        "%s get_top_fund_stocks: 上游 %s 列错位（%s 列非 6 位代码，"
                        "实测样例 %r）——拒绝返回不可信数据",
                        self.name, report_symbol, col, df[col].head(3).tolist(),
                    )
                    return None

            df = df.head(max(1, int(limit or 50)))
            records = _df_records(df)
            return MarketData(
                data_type='top_fund_stocks',
                data={'fund_type': report_symbol, 'stocks': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"{self.name} get_top_fund_stocks failed: {e}")
            return None

    def get_stock_comment(self, symbol: str) -> Optional[MarketData]:
        """个股千股千评（东财 stock_comment_em，全市场 5196 行按代码过滤）。

        返回的是**机构参与度 / 综合得分 / 换手率 / 市盈率 / 主力成本**等指标 ——
        这是指标的来源，调用方不得把它描述成「情绪分类」。
        """
        try:
            import akshare as ak

            df = _cached_market_df('stock_comment', ak.stock_comment_em)
            if df is None or df.empty:
                return None

            bare = str(symbol or '').split('.')[0]
            code_cols = [c for c in df.columns if str(c) in ('代码', '股票代码')]
            if not code_cols:
                logger.warning(f"{self.name} get_stock_comment: 未找到代码列 {list(df.columns)[:6]}")
                return None
            col = code_cols[0]
            sub = df[df[col].astype(str).str.zfill(6) == bare]
            if sub.empty:
                return MarketData(
                    data_type='stock_comment',
                    data={'symbol': symbol, 'comment': None, 'empty': True},
                    source=self.name,
                    timestamp=datetime.now().isoformat(),
                )
            row = sub.astype(object).where(sub.notna(), None).iloc[0].to_dict()
            return MarketData(
                data_type='stock_comment',
                data={'symbol': symbol, 'comment': row, 'empty': False},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"{self.name} get_stock_comment failed: {e}")
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

            # 2026-09-01 修复：akshare 1.18.81 的 stock_lhb_stock_statistic_em 签名已变更
            # （symbol 参数为周期如'近一月'，不再接受 start_date/end_date），调用必 TypeError。
            # 每日龙虎榜榜单的正确接口是 stock_lhb_detail_em(start_date, end_date)（YYYYMMDD）。
            compact = date.replace('-', '')
            df = ak.stock_lhb_detail_em(start_date=compact, end_date=compact)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No daily LHB data for {date}")
                return None

            # 清理 NaN（龙虎榜部分记录数字字段为 NaN，直接 to_dict 会让 JSON 序列化炸：
            # ValueError: Out of range float values are not JSON compliant: nan）
            lhb_data = df.astype(object).where(df.notna(), None).to_dict('records')

            return MarketData(
                data_type='lhb_daily',
                data={'date': date, 'records': lhb_data, 'total': len(lhb_data)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_daily failed: {e}")
            return None
