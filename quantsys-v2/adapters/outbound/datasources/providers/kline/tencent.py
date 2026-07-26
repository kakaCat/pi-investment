"""Tencent kline provider - 腾讯K线数据源（国内直连，绕代理）

背景（2026-07-23）：eastmoney（akshare）K线 API push2his.eastmoney.com
被 eastmoney 封禁本机 IP（直连/代理均 TCP RST），腾讯 ifzq.gtimg.cn
端点实测可用，作为 K线网络源的首选。
"""
import logging
from typing import List, Optional
from datetime import datetime

import requests

from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

logger = logging.getLogger(__name__)


class TencentKlineProvider(KlineProvider):
    """Kline provider using Tencent ifzq.gtimg.cn API (daily only)"""

    # 国内数据源，必须绕过本机代理（ClashX 国外出口会被重置）
    _NO_PROXY = {'http': None, 'https': None}
    _URL = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'

    @property
    def name(self) -> str:
        return "tencent"

    @staticmethod
    def _to_tencent_code(symbol: str) -> Optional[str]:
        """600519 -> sh600519, 300001 -> sz300001, 920xxx -> bj920xxx, 399006(指数) -> sz399006"""
        symbol = symbol.split('.')[0]  # 容忍 600519.SH 形式
        if symbol.startswith(('60', '68', '11', '51')):
            return f'sh{symbol}'
        # '39' 为深市指数代码段（399001 深成指、399006 创业板指）
        if symbol.startswith(('00', '30', '12', '15', '39')):
            return f'sz{symbol}'
        if symbol.startswith(('4', '8', '92')):
            return f'bj{symbol}'
        return None

    def get_klines(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[KlineData]]:
        """Get daily kline data from Tencent

        Returns:
            List of KlineData if successful, None if failed
        """
        if period != 'daily':
            logger.debug(f"Tencent provider only supports daily, got: {period}")
            return None

        code = self._to_tencent_code(symbol)
        if not code:
            logger.warning(f"Cannot map symbol to tencent code: {symbol}")
            return None

        try:
            resp = requests.get(
                self._URL,
                params={'param': f'{code},day,{start_date},{end_date},320,qfq'},
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
                proxies=self._NO_PROXY,
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()

            if payload.get('code') != 0:
                logger.warning(f"Tencent API error for {symbol}: {payload.get('msg')}")
                return None

            node = payload.get('data', {}).get(code) or {}
            # 前复权键为 qfqday；无复权数据时退化为 day
            rows = node.get('qfqday') or node.get('day') or []
            if not rows:
                logger.warning(f"Tencent returned no data for {symbol}")
                return None

            result = []
            prev_close = None
            for row in rows:
                # 字段顺序: [date, open, close, high, low, volume(手)]
                date_str, open_p, close, high, low, volume = (
                    row[0], float(row[1]), float(row[2]),
                    float(row[3]), float(row[4]), int(float(row[5])),
                )
                change_pct = (
                    round((close - prev_close) / prev_close * 100, 2)
                    if prev_close else 0.0
                )
                prev_close = close

                result.append(KlineData(
                    symbol=symbol,
                    date=date_str,
                    open=open_p,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    change_pct=change_pct,
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            logger.info(f"Tencent provider returned {len(result)} klines for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Tencent kline provider failed for {symbol}: {e}")
            return None
