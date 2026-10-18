"""交易状态值对象（下单前硬约束）

RFC 015 §4.1（2026-09-11 REQ-cf627b）：把「stocks 表基础状态」与「实时行情」
两类输入裁决为一个不可变值对象，供下单前置校验 fail-closed 使用。

领域层零外部依赖（仅 dataclasses）。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TradingStatus:
    """交易状态（值对象，不可变）

    Attributes:
        symbol: 股票代码（6 位）
        is_st: 是否 ST/*ST（影响涨跌幅限制，ST 可交易但限幅 5%）
        is_suspended: 是否停牌/退市（保守裁决：基础状态或行情任一判停即停）
        limit_up: 现价是否触及涨停价（涨停难以买入）
        limit_down: 现价是否触及跌停价（卖出难以成交）
        tradeable: 是否可下单（= 未停牌 且 非涨停 且 无跨源冲突）
        reason: 判定依据（含冲突时以 'conflict' 关键字标注）
        as_of: 判定时点（ISO8601）
        prev_close: 昨收价（涨跌停基准）
        limit_ratio: 该标的的涨跌幅限制比例（0.05 / 0.10 / 0.20）
    """
    symbol: str
    is_st: bool
    is_suspended: bool
    limit_up: bool
    limit_down: bool
    tradeable: bool
    reason: str
    as_of: str
    prev_close: float
    limit_ratio: float

    def to_dict(self) -> dict:
        """序列化（API/工具层统一用 dict 输出）"""
        return {
            'symbol': self.symbol,
            'is_st': self.is_st,
            'is_suspended': self.is_suspended,
            'limit_up': self.limit_up,
            'limit_down': self.limit_down,
            'tradeable': self.tradeable,
            'reason': self.reason,
            'as_of': self.as_of,
            'prev_close': self.prev_close,
            'limit_ratio': self.limit_ratio,
            'limit_up_price': round(self.prev_close * (1 + self.limit_ratio), 2) if self.prev_close else None,
            'limit_down_price': round(self.prev_close * (1 - self.limit_ratio), 2) if self.prev_close else None,
        }
