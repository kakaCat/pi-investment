"""新浪财经 K 线数据提供者

新浪财经 K 线接口：稳定可靠，适合作为主力数据源之一
API: https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData

2026-09-02: 创建，用于替代失效的 Baostock/Tencent/Eastmoney
"""
import logging
from typing import List, Optional
from datetime import datetime
import requests

from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

logger = logging.getLogger(__name__)


class SinaKlineProvider(KlineProvider):
    """新浪财经 K 线数据提供者"""

    # 国内数据源，避免走代理
    _NO_PROXY = {'http': None, 'https': None}
    _URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"

    @property
    def name(self) -> str:
        return "sina"

    def __init__(self):
        # 最近一次失败的具体原因，供 DataProviderManager 聚合返回
        self.last_error: Optional[str] = None

    @staticmethod
    def _to_sina_code(symbol: str) -> str:
        """转换股票代码格式

        601857 -> sh601857
        000001 -> sz000001
        """
        symbol = symbol.split('.')[0]  # 容忍 600519.SH 形式
        if symbol.startswith(('60', '68', '11', '51')):
            return f'sh{symbol}'
        elif symbol.startswith(('00', '30', '12', '15', '39')):
            return f'sz{symbol}'
        elif symbol.startswith(('4', '8', '92')):
            return f'bj{symbol}'
        else:
            return f'sz{symbol}'  # 默认深市

    @staticmethod
    def _convert_period(period: str) -> str:
        """转换周期参数

        daily -> 240 (日线)
        weekly -> 1200 (周线)
        monthly -> 7200 (月线)
        """
        period_map = {
            'daily': '240',
            'day': '240',
            'weekly': '1200',
            'week': '1200',
            'monthly': '7200',
            'month': '7200',
        }
        return period_map.get(period.lower(), '240')

    def get_klines(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[KlineData]]:
        """获取 K 线数据

        Args:
            symbol: 股票代码，如 601857
            period: 周期，daily/weekly/monthly
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            List[KlineData] if successful, None if failed
        """
        self.last_error = None

        try:
            sina_code = self._to_sina_code(symbol)
            scale = self._convert_period(period)

            # 新浪接口返回最近 N 条数据，默认获取 300 条（约一年多）
            datalen = 300

            params = {
                'symbol': sina_code,
                'scale': scale,
                'ma': 'no',  # 不需要均线
                'datalen': datalen
            }

            response = requests.get(
                self._URL,
                params=params,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'},
                proxies=self._NO_PROXY,
                timeout=10
            )

            if response.status_code != 200:
                self.last_error = f'HTTP {response.status_code}'
                logger.warning(f"Sina kline provider failed for {symbol}: {self.last_error}")
                return None

            # 解析 JSON 响应
            import json
            data = json.loads(response.text)

            if not data or not isinstance(data, list):
                self.last_error = '返回数据为空或格式错误'
                logger.warning(f"Sina kline provider failed for {symbol}: {self.last_error}")
                return None

            # 转换为 KlineData 对象列表
            klines = []
            for item in data:
                try:
                    date_str = item.get('day', '')

                    # 日期过滤
                    if start_date and date_str < start_date:
                        continue
                    if end_date and date_str > end_date:
                        continue

                    # volume 为成交量（手），需要转换为股（×100）
                    volume_raw = float(item.get('volume', 0))
                    volume = int(volume_raw * 100) if volume_raw > 0 else 0

                    kline = KlineData(
                        symbol=symbol,
                        date=date_str,
                        open=float(item.get('open', 0)),
                        high=float(item.get('high', 0)),
                        low=float(item.get('low', 0)),
                        close=float(item.get('close', 0)),
                        volume=volume,
                        source='sina',
                        timestamp=datetime.now().isoformat()
                    )
                    klines.append(kline)
                except (ValueError, TypeError, KeyError) as e:
                    logger.debug(f"Skipping invalid kline data for {symbol}: {e}")
                    continue

            if not klines:
                self.last_error = '过滤后数据为空'
                return None

            # 按日期排序
            klines.sort(key=lambda x: x.date)

            logger.info(f"Sina kline provider success for {symbol}: {len(klines)} records")
            return klines

        except requests.exceptions.Timeout:
            self.last_error = '请求超时（>10s）'
            logger.warning(f"Sina kline provider timeout for {symbol}")
            return None

        except requests.exceptions.RequestException as e:
            self.last_error = f'网络异常: {type(e).__name__}: {e}'
            logger.warning(f"Sina kline provider failed for {symbol}: {self.last_error}")
            return None

        except Exception as e:
            self.last_error = f'解析异常: {type(e).__name__}: {e}'
            logger.error(f"Sina kline provider error for {symbol}: {e}", exc_info=True)
            return None
