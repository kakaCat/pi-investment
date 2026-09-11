# domain/trading/ports/IMinuteKlineProvider.py
"""分钟线数据源端口（一类一文件，对齐 domain/trading/ports 既有组织方式）

RFC 015 §4.3：分钟线 provider 的多源契约。实现方（出站适配器）必须：
1. 提供唯一 name（注册进 DataProviderManager 的 minute_kline_providers）
2. 失败返回 None 并写入 last_error（失败与空结果语义分离：失败 fail-loud，
   空结果是「该源无数据」，由 manager 继续降级到下一源）
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.market_data import MinuteKline


class IMinuteKlineProvider(ABC):
    """分钟线 provider 抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称（唯一，用于日志与 source 归因）"""
        pass

    @abstractmethod
    def get_minute_klines(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Optional[List[MinuteKline]]:
        """获取分钟K线

        Args:
            symbol: 股票代码（6 位，容忍 600519.SH 形式）
            period: 周期，接受 '1m'/'5m'/'15m'/'30m'/'60m' 或裸数字 '1'/'5'/'15'/'30'/'60'
            start_date: 起始日期 'YYYY-MM-DD'（可空；上游多为「最近 N 根」接口，
                        实现方负责按需多取再过滤）
            end_date: 结束日期 'YYYY-MM-DD'（可空）
            limit: 期望返回的最大K线根数

        Returns:
            成功返回 List[MinuteKline]（可为空列表 = 该源无数据）；
            失败返回 None（必须同时在 self.last_error 写明原因）
        """
        pass
