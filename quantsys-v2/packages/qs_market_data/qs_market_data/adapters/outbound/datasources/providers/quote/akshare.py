"""
AkShare quote provider implementation
"""
import os
import akshare as ak
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import patch

from qs_market_data.adapters.outbound.datasources.base import QuoteProvider
from qs_market_data.adapters.outbound.datasources.models import QuoteData


class AkshareQuoteProvider(QuoteProvider):
    """Quote provider using AkShare data source"""

    @property
    def name(self) -> str:
        """Provider name"""
        return "akshare"

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get real-time quote for a stock

        Args:
            symbol: Stock symbol (6-digit for A-shares, 1-5 digits or .HK suffix for HK stocks)

        Returns:
            QuoteData if found, None if not found

        Raises:
            Exception: If akshare API call fails
        """
        # Disable proxy by patching environment variables before akshare makes requests
        # This ensures akshare's internal requests session doesn't use proxy
        self.last_error = None
        env_patch = {
            'HTTP_PROXY': '',
            'HTTPS_PROXY': '',
            'http_proxy': '',
            'https_proxy': ''
        }

        try:
            with patch.dict(os.environ, env_patch, clear=False):
                # Detect A-share vs HK stock
                # A-share: 6-digit code (e.g., 600000)
                # HK stock: 1-5 digits (e.g., 00700) or .HK suffix (e.g., 0700.HK)
                if symbol.endswith('.HK') or (symbol.isdigit() and len(symbol) <= 5):
                    return self._get_hk_quote(symbol)
                else:
                    return self._get_a_quote(symbol)
        except Exception as e:
            raise Exception(f"akshare 查询失败: {e}") from e

    def get_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """批量实时行情（2026-11-12，w-09d7af23）

        背景（实测事故）：此前继承基类默认实现 = 逐只调 get_quote，而每只都跑一次
        `ak.stock_zh_a_spot_em()`（拉全市场行情表再过滤）——7 只持仓 = 7 次全市场抓取，
        盘前东财接口慢时共挂 44s，把上游 agent 工具（20s 超时）拖死。

        实现：A 股**一次** `stock_zh_a_spot_em()` 抓取后本地过滤全部目标代码（7 次请求 → 1 次）；
        港股标的不在本表内，退回逐只 `get_quote`（港股场景极少，成本可忽略）。

        约定（与 manager.get_quotes 契约一致）：
          - 只返回成功且非空的标的；未返回 ≠ 无行情；
          - 整批一只都没拿到时必须自报 last_error（否则 manager 会记 empty 而非 failure，
            健康分不掉、排序永远第一，重演本次事故）。
        """
        self.last_error = None
        out: Dict[str, QuoteData] = {}
        a_symbols = [s for s in symbols
                     if not (s.endswith('.HK') or (s.isdigit() and len(s) <= 5))]
        hk_symbols = [s for s in symbols if s not in a_symbols]

        if a_symbols:
            got = self._batch_a_quotes(a_symbols)
            out.update(got)
            if not got:
                # 要么全市场表为空（无数据），要么内部已置 last_error（真失败）
                if not self.last_error:
                    self.last_error = (
                        f"akshare A股批量无数据（{len(a_symbols)} 只全未命中，"
                        "stock_zh_a_spot_em 返回空表或代码均不存在）"
                    )

        for symbol in hk_symbols:
            try:
                quote = self.get_quote(symbol)
            except Exception as e:
                self.last_error = f"akshare 港股 {symbol} 查询失败: {e}"
                continue
            if quote is not None:
                out[symbol] = quote
            else:
                # get_quote 内部已自报 last_error（无数据场景）
                pass

        return out

    def _batch_a_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """一次 stock_zh_a_spot_em() 拉全市场表，本地过滤目标代码。

        Returns:
            {symbol: QuoteData}，只含命中的标的；失败抛异常（由调用方记 last_error）。
        """
        wanted = {s.split('.')[0] for s in symbols}
        env_patch = {
            'HTTP_PROXY': '',
            'HTTPS_PROXY': '',
            'http_proxy': '',
            'https_proxy': ''
        }
        with patch.dict(os.environ, env_patch, clear=False):
            df = ak.stock_zh_a_spot_em()

        if df is None or df.empty or '代码' not in df.columns:
            return {}

        rows = df[df['代码'].isin(wanted)]
        out: Dict[str, QuoteData] = {}
        for _, data in rows.iterrows():
            code = str(data['代码'])
            try:
                out[code] = QuoteData(
                    symbol=code,
                    name=str(data['名称']),
                    price=float(data['最新价']),
                    open=float(data['今开']),
                    high=float(data['最高']),
                    low=float(data['最低']),
                    prev_close=float(data['昨收']),
                    volume=int(data['成交量']),
                    amount=float(data['成交额']),
                    change_pct=float(data['涨跌幅']),
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                )
            except (KeyError, TypeError, ValueError) as e:
                # 单只字段缺失/格式异常不拖垮整批；但最后若一只都没成，要向 manager 暴露失败
                if not self.last_error:
                    self.last_error = f"akshare A股批量字段解析失败: {e}"
        return out

    def _get_a_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get A-share quote using akshare.stock_zh_a_spot_em()

        Args:
            symbol: 6-digit A-share code (e.g., 600000)

        Returns:
            QuoteData if found, None if not found
        """
        # Remove any suffix for A-shares
        clean_symbol = symbol.split('.')[0]

        # Get all A-share quotes
        df = ak.stock_zh_a_spot_em()

        # Filter by symbol
        row = df[df['代码'] == clean_symbol]

        if row.empty:
            self.last_error = f"akshare A股无 {clean_symbol} 数据（代码不存在或已退市）"
            return None

        # Extract data from first row
        data = row.iloc[0]

        try:
            return QuoteData(
                symbol=clean_symbol,
                name=str(data['名称']),
                price=float(data['最新价']),
                open=float(data['今开']),
                high=float(data['最高']),
                low=float(data['最低']),
                prev_close=float(data['昨收']),
                volume=int(data['成交量']),
                amount=float(data['成交额']),
                change_pct=float(data['涨跌幅']),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )
        except KeyError as e:
            raise Exception(f"akshare A股数据格式变化，缺少字段: {e}") from e

    def _get_hk_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get HK stock quote using akshare.stock_hk_spot_em()

        Args:
            symbol: HK stock code (e.g., 00700 or 0700.HK)

        Returns:
            QuoteData if found, None if not found
        """
        # Remove .HK suffix if present
        clean_symbol = symbol.replace('.HK', '')

        # Pad to 5 digits with leading zeros
        clean_symbol = clean_symbol.zfill(5)

        # Get all HK stock quotes
        df = ak.stock_hk_spot_em()

        # Filter by symbol
        row = df[df['代码'] == clean_symbol]

        if row.empty:
            self.last_error = f"akshare 港股无 {clean_symbol} 数据（代码不存在或未上市）"
            return None

        # Extract data from first row
        data = row.iloc[0]

        try:
            return QuoteData(
                symbol=clean_symbol,
                name=str(data['名称']),
                price=float(data['最新价']),
                open=float(data['今开']),
                high=float(data['最高']),
                low=float(data['最低']),
                prev_close=float(data['昨收']),
                volume=int(data['成交量']),
                amount=None,  # HK data doesn't have 成交额
                change_pct=float(data['涨跌幅']),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )
        except KeyError as e:
            raise Exception(f"akshare 港股数据格式变化，缺少字段: {e}") from e
