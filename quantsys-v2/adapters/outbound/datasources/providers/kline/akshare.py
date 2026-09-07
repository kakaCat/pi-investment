"""AkShare kline provider - fallback source"""
import os
import logging
from typing import List, Optional
from datetime import datetime
from unittest.mock import patch

from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

logger = logging.getLogger(__name__)


class AkshareKlineProvider(KlineProvider):
    """Kline provider using AkShare API"""

    @property
    def name(self) -> str:
        return "akshare"

    def __init__(self):
        # 最近一次失败的具体原因，供 DataProviderManager 聚合返回给调用方
        self.last_error: Optional[str] = None

    def get_klines(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[KlineData]]:
        """Get kline data from AkShare

        Args:
            symbol: Stock symbol
            period: Period (daily, weekly, monthly, 1m, 5m, 15m, 30m, 60m)
            start_date: Start date (YYYY-MM-DD or YYYYMMDD)
            end_date: End date (YYYY-MM-DD or YYYYMMDD)

        Returns:
            List of KlineData if successful, None if failed
        """
        self.last_error = None

        # Disable proxy for AkShare
        env_patch = {
            'HTTP_PROXY': '',
            'HTTPS_PROXY': '',
            'http_proxy': '',
            'https_proxy': ''
        }

        try:
            with patch.dict(os.environ, env_patch, clear=False):
                import akshare as ak

                # Normalize date format (AkShare expects YYYYMMDD)
                start_date_normalized = start_date.replace('-', '')
                end_date_normalized = end_date.replace('-', '')

                # Map period to AkShare period parameter
                period_map = {
                    'daily': 'daily',
                    'weekly': 'weekly',
                    'monthly': 'monthly',
                    '1m': '1',
                    '5m': '5',
                    '15m': '15',
                    '30m': '30',
                    '60m': '60'
                }

                akshare_period = period_map.get(period)
                if not akshare_period:
                    self.last_error = f"不支持的周期: {period}"
                    logger.warning(f"Unsupported period for AkShare: {period}")
                    return None

                # Fetch data based on period type
                if period in ['1m', '5m', '15m', '30m', '60m']:
                    # Intraday data
                    df = ak.stock_zh_a_hist_min_em(
                        symbol=symbol,
                        period=akshare_period,
                        start_date=start_date_normalized,
                        end_date=end_date_normalized,
                        adjust='qfq'
                    )
                else:
                    # Daily/weekly/monthly data
                    df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period=akshare_period,
                        start_date=start_date_normalized,
                        end_date=end_date_normalized,
                        adjust='qfq'
                    )

                if df is None or df.empty:
                    self.last_error = (
                        f"akshare(eastmoney) 无 {symbol} 数据"
                        "（代码不存在，或该接口仅支持个股、不支持指数）"
                    )
                    logger.warning(f"AkShare returned no data for {symbol}")
                    return None

                # Convert to KlineData list
                result = []
                for i, row in df.iterrows():
                    # Column names differ between daily and minute data
                    date_col = '日期' if '日期' in df.columns else '时间'
                    open_col = '开盘' if '开盘' in df.columns else '开盘价'
                    close_col = '收盘' if '收盘' in df.columns else '收盘价'
                    high_col = '最高' if '最高' in df.columns else '最高价'
                    low_col = '最低' if '最低' in df.columns else '最低价'
                    volume_col = '成交量' if '成交量' in df.columns else '成交量'

                    date_str = str(row[date_col])
                    close = float(row[close_col])
                    open_p = float(row[open_col])
                    high = float(row[high_col])
                    low = float(row[low_col])
                    # 成交量单位为手，归一为股（契约单位）
                    volume = int(row[volume_col]) * 100
                    # 成交额：日K 有成交额列直接用；否则按 股×收盘价 估算
                    amount = (
                        float(row['成交额']) if '成交额' in df.columns
                        else volume * close
                    )

                    # Calculate change_pct
                    if i > 0:
                        prev_close = float(df.iloc[i-1][close_col])
                        change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
                    else:
                        change_pct = 0.0

                    result.append(KlineData(
                        symbol=symbol,
                        date=date_str,
                        open=open_p,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                        change_pct=change_pct,
                        amount=amount,
                        source=self.name,
                        timestamp=datetime.now().isoformat()
                    ))

                logger.info(f"AkShare provider returned {len(result)} klines for {symbol}")
                return result

        except Exception as e:
            self.last_error = f"akshare(eastmoney) 调用失败: {type(e).__name__}: {e}"
            logger.error(f"AkShare kline provider failed for {symbol}: {e}")
            return None
