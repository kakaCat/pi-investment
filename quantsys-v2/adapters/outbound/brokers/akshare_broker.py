"""
AkShare Broker Adapter

AkShare 是一个开源的金融数据接口库，提供 A 股、港股、美股等市场数据。
本适配器将 AkShare 封装为统一的券商接口。

注意：AkShare 仅提供数据，不支持交易功能。
"""

import logging
from typing import List, Optional
from datetime import datetime
import pandas as pd

from domain.brokers import BaseBroker
from domain.brokers.trading_types import (
    BrokerProfile,
    ApiResponse,
    BrokerQuote,
    BrokerCandle,
    CredentialFieldDef,
    CredentialField,
)

logger = logging.getLogger(__name__)


class AkshareBroker(BaseBroker):
    """
    AkShare 数据源适配器

    特点：
    - 免费开源，无需 API Key
    - 支持 A 股实时行情和历史数据
    - 不支持交易功能
    """

    def __init__(self):
        """初始化 AkShare 适配器"""
        self._akshare = None
        self._load_akshare()

    def _load_akshare(self):
        """延迟加载 akshare 库"""
        try:
            import akshare as ak
            self._akshare = ak
            logger.info("AkShare library loaded successfully")
        except ImportError:
            logger.error("AkShare library not found. Install with: pip install akshare")
            raise

    # ========================================================================
    # Identity & Configuration
    # ========================================================================

    def get_id(self) -> str:
        """返回券商 ID"""
        return "akshare"

    def get_name(self) -> str:
        """返回券商名称"""
        return "AkShare"

    def get_profile(self) -> BrokerProfile:
        """返回券商配置"""
        return BrokerProfile(
            id="akshare",
            display_name="AkShare (开源数据)",
            region="CN",
            currency="CNY",
            credential_fields=[],  # 无需凭证
            supported_exchanges=["SSE", "SZSE", "BSE"],  # 上交所、深交所、北交所
            product_types=[],
            supports_intraday=True,
            supports_margin=False,
            supports_options=False,
            has_native_paper=False,
            default_paper_balance=1000000.0,
            default_watchlist=[
                "600000",  # 浦发银行
                "000001",  # 平安银行
                "600036",  # 招商银行
                "000858",  # 五粮液
                "601318",  # 中国平安
            ],
            default_symbol="600000",
            default_exchange="SSE",
            brokerage_info="免费开源数据源",
        )

    # ========================================================================
    # Market Data
    # ========================================================================

    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表，支持格式：
                - "600000" (自动识别交易所)
                - "600000.SH"
                - "000001.SZ"

        Returns:
            ApiResponse[List[BrokerQuote]]: 行情数据
        """
        if not self._akshare:
            return ApiResponse.fail("AkShare library not loaded")

        try:
            # 获取实时行情数据（东方财富）
            df = self._akshare.stock_zh_a_spot_em()

            quotes = []
            for symbol in symbols:
                # 标准化股票代码（去除交易所后缀）
                clean_symbol = symbol.split('.')[0]

                # 查找对应行情
                row = df[df['代码'] == clean_symbol]
                if row.empty:
                    logger.warning(f"Symbol not found: {symbol}")
                    continue

                row = row.iloc[0]

                # 构建 BrokerQuote
                quote = BrokerQuote(
                    symbol=symbol,
                    last_price=float(row['最新价']),
                    open_price=float(row['今开']),
                    high_price=float(row['最高']),
                    low_price=float(row['最低']),
                    close_price=float(row['昨收']),
                    volume=float(row['成交量']),
                    turnover=float(row['成交额']),
                    change=float(row['涨跌额']),
                    change_pct=float(row['涨跌幅']),
                    timestamp=datetime.now(),
                )
                quotes.append(quote)

            if not quotes:
                return ApiResponse.fail(f"No quotes found for symbols: {symbols}")

            return ApiResponse.ok(quotes)

        except Exception as e:
            logger.error(f"Failed to get quotes: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get quotes: {str(e)}")

    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily"
    ) -> ApiResponse[List[BrokerCandle]]:
        """
        获取历史K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            frequency: 频率，支持 "daily", "weekly", "monthly"

        Returns:
            ApiResponse[List[BrokerCandle]]: K线数据
        """
        if not self._akshare:
            return ApiResponse.fail("AkShare library not loaded")

        try:
            # 标准化股票代码
            clean_symbol = symbol.split('.')[0]

            # 根据频率选择接口
            period_map = {
                "daily": "daily",
                "weekly": "weekly",
                "monthly": "monthly",
            }
            period = period_map.get(frequency, "daily")

            # 清除代理环境变量（akshare 需要直连）
            import os
            old_proxies = {}
            for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
                if key in os.environ:
                    old_proxies[key] = os.environ.pop(key)

            try:
                # 首先尝试 akshare（东方财富）
                df = None
                try:
                    # 超时保护包装 akshare 调用
                    # 2026-09-11 修复（w-f4aa1f6a）：原实现无条件用 signal.alarm 做超时，
                    # 但 signal 只能在**主线程**注册——该路径会被 FastAPI 线程池 / 后台任务线程调用，
                    # 于是抛 "signal only works in main thread of the main interpreter"，
                    # 直接把 AkShare→Sina 回退链打断（实证 error_event 9223e5b2 / 5da6019a /
                    # 306a35ea，及 96 次 traceback 的源头）。现按线程角色分流：
                    #   主线程   → 沿用 signal（开销最低、语义与原实现一致）
                    #   非主线程 → 线程池 + future.result(timeout=30)，线程安全且超时语义等价
                    import platform
                    import threading

                    def _call_akshare():
                        return self._akshare.stock_zh_a_hist(
                            symbol=clean_symbol,
                            period=period,
                            start_date=start_date.replace('-', ''),
                            end_date=end_date.replace('-', ''),
                            adjust="qfq"  # 前复权
                        )

                    _use_signal = platform.system() != 'Windows' and threading.current_thread() is threading.main_thread()
                    if _use_signal:
                        import signal

                        def timeout_handler(signum, frame):
                            raise TimeoutError(f"AkShare request timeout after 30s for {symbol}")

                        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(30)  # 30秒超时
                        try:
                            df = _call_akshare()
                            logger.info(f"[BROKER] AkShare succeeded for {symbol}")
                        finally:
                            signal.alarm(0)  # 取消超时
                            signal.signal(signal.SIGALRM, old_handler)
                    else:
                        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

                        with ThreadPoolExecutor(max_workers=1) as _pool:
                            _fut = _pool.submit(_call_akshare)
                            try:
                                df = _fut.result(timeout=30)  # 非主线程安全超时
                                logger.info(f"[BROKER] AkShare succeeded for {symbol} (thread-safe timeout path)")
                            except FuturesTimeoutError:
                                raise TimeoutError(f"AkShare request timeout after 30s for {symbol}")

                except TimeoutError as timeout_err:
                    logger.warning(f"[BROKER] AkShare timeout for {symbol}, falling back to Sina: {timeout_err}")

                    # 回退到新浪财经 API
                    try:
                        logger.info(f"Falling back to Sina Finance API for {symbol}")
                        df = self._fetch_from_sina(clean_symbol, start_date, end_date, period)
                        logger.info(f"[BROKER] Sina Finance succeeded for {symbol}")
                    except Exception as sina_error:
                        logger.error(f"[BROKER] Sina Finance also failed for {symbol}: {sina_error}")
                        raise Exception(f"AkShare timeout and Sina Finance failed. Timeout: {timeout_err}, Sina: {sina_error}")

                except Exception as e:
                    logger.warning(f"[BROKER] AkShare failed for {symbol}, falling back to Sina: {e}")

                    # 回退到新浪财经 API
                    try:
                        logger.info(f"Falling back to Sina Finance API for {symbol}")
                        df = self._fetch_from_sina(clean_symbol, start_date, end_date, period)
                        logger.info(f"[BROKER] Sina Finance succeeded for {symbol}")
                    except Exception as sina_error:
                        logger.error(f"[BROKER] Sina Finance also failed for {symbol}: {sina_error}")
                        raise Exception(f"Both AkShare and Sina Finance failed. AkShare: {e}, Sina: {sina_error}")
            finally:
                # 恢复代理环境变量
                os.environ.update(old_proxies)

            if df.empty:
                return ApiResponse.fail(f"No history data for {symbol}")

            # 转换为 BrokerCandle
            candles = []
            for _, row in df.iterrows():
                candle = BrokerCandle(
                    symbol=symbol,
                    timestamp=pd.to_datetime(row['日期']),
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=float(row['成交量']),
                    turnover=float(row['成交额']) if '成交额' in row else None,
                )
                candles.append(candle)

            return ApiResponse.ok(candles)

        except Exception as e:
            logger.error(f"Failed to get history: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get history: {str(e)}")

    def _fetch_from_sina(self, clean_symbol: str, start_date: str, end_date: str, period: str) -> pd.DataFrame:
        """
        从新浪财经 API 获取历史数据（备用数据源）

        Args:
            clean_symbol: 去除后缀的股票代码（如 600519）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            period: 频率（daily/weekly/monthly）

        Returns:
            DataFrame: 与 akshare 格式兼容的数据
        """
        import requests
        import json
        from datetime import datetime

        # 转换为新浪代码格式
        # 沪市: 6开头 -> sh
        # 深市: 0/3开头 -> sz
        # 北交所: 4/8/9开头 -> bj
        if clean_symbol.startswith('6'):
            sina_symbol = f'sh{clean_symbol}'
        elif clean_symbol.startswith(('0', '3')):
            sina_symbol = f'sz{clean_symbol}'
        elif clean_symbol.startswith(('4', '8', '9')):
            sina_symbol = f'bj{clean_symbol}'
        else:
            # 默认使用沪市
            sina_symbol = f'sh{clean_symbol}'

        # 新浪财经历史数据 API
        # scale: 5=5分钟, 15=15分钟, 30=30分钟, 60=60分钟, 240=日线, 1440=周线
        scale_map = {
            'daily': '240',
            'weekly': '1440',
            'monthly': '1440'  # 新浪没有月线，用周线代替
        }
        scale = scale_map.get(period, '240')

        # 计算需要多少条数据
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        days_diff = (end_dt - start_dt).days
        datalen = max(days_diff + 10, 1024)  # 多取一些数据以确保覆盖范围

        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            'symbol': sina_symbol,
            'scale': scale,
            'datalen': datalen
        }

        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"Sina API returned status {resp.status_code}")

        data = json.loads(resp.text)
        if not data:
            raise Exception("Sina API returned empty data")

        # 转换为 DataFrame
        df = pd.DataFrame(data)

        # 过滤日期范围
        df['day'] = pd.to_datetime(df['day'])
        df = df[(df['day'] >= start_date) & (df['day'] <= end_date)]

        # 重命名列以匹配 akshare 格式
        df = df.rename(columns={
            'day': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '成交量'
        })

        # 确保数值类型
        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 添加缺失列
        df['成交额'] = 0  # 新浪接口没有成交额数据

        return df

    # ========================================================================
    # Symbol Search
    # ========================================================================

    def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> ApiResponse[List[dict]]:
        """
        搜索股票

        Args:
            query: 搜索关键词（代码或名称）
            exchange: 交易所过滤，可选

        Returns:
            ApiResponse[List[dict]]: 搜索结果
        """
        if not self._akshare:
            return ApiResponse.fail("AkShare library not loaded")

        try:
            # 获取股票列表
            df = self._akshare.stock_zh_a_spot_em()

            # 搜索匹配
            query_lower = query.lower()
            mask = (
                df['代码'].str.contains(query_lower, case=False, na=False) |
                df['名称'].str.contains(query_lower, case=False, na=False)
            )
            results_df = df[mask]

            # 交易所过滤
            if exchange:
                if exchange.upper() == "SSE":
                    results_df = results_df[results_df['代码'].str.startswith('6')]
                elif exchange.upper() == "SZSE":
                    results_df = results_df[
                        results_df['代码'].str.startswith('0') |
                        results_df['代码'].str.startswith('3')
                    ]

            # 限制结果数量
            results_df = results_df.head(20)

            # 转换为字典列表
            results = []
            for _, row in results_df.iterrows():
                results.append({
                    'symbol': row['代码'],
                    'name': row['名称'],
                    'exchange': self._infer_exchange(row['代码']),
                    'last_price': float(row['最新价']),
                    'change_pct': float(row['涨跌幅']),
                })

            return ApiResponse.ok(results)

        except Exception as e:
            logger.error(f"Failed to search symbols: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to search symbols: {str(e)}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _infer_exchange(self, symbol: str) -> str:
        """
        根据股票代码推断交易所

        Args:
            symbol: 股票代码

        Returns:
            str: 交易所代码 "SSE"/"SZSE"/"BSE"
        """
        if symbol.startswith('6'):
            return "SSE"  # 上交所
        elif symbol.startswith('0') or symbol.startswith('3'):
            return "SZSE"  # 深交所
        elif symbol.startswith('8') or symbol.startswith('4'):
            return "BSE"  # 北交所
        else:
            return "UNKNOWN"
