"""分钟K线仓储（薄封装既有 KlineORMRepository 的分钟线方法，不重写 SQL）

RFC 015 §4.1（2026-09-11 REQ-cf627b）：
- 存储是既有表 quant.minute_klines（主键 (symbol, trade_datetime)，**无 period 列**）
- 既有实现 adapters/outbound/repositories/kline_repository.py 的
  get_minute_klines / get_latest_minute_kline / batch_insert_minute_klines 直接复用，
  本类只做「领域模型 ↔ ORM/DataFrame」的边界转换，不新增 SQL。

粒度说明：表无 period 列 → 落库数据无法声明自己的周期。本仓储把 period 留空
（''），由 provider/服务层按数据自身的时间间隔推断（见 granularity_label）。
"""
from datetime import datetime
from typing import List, Optional

from domain.models.market_data import MinuteKline
from domain.trading.ports.IMinuteKlineRepository import IMinuteKlineRepository

from infrastructure.persistence.orm.models import MinuteKline as MinuteKlineORM


def _parse_dt(value) -> Optional[datetime]:
    """'YYYY-MM-DD HH:MM:SS' / datetime → datetime（不可解析返回 None）"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:19] if len(text) >= 19 else text, fmt)
        except ValueError:
            continue
    return None


def granularity_label(klines: List[MinuteKline]) -> str:
    """按数据自身的时间间隔推断粒度（'1m'/'5m'/... 推断不出返回 ''）

    只取同一自然日内相邻两点的间隔众数；跨日间隔天然很大，故按日分组。
    推断不出（样本 <3 或间隔不收敛）时返回空串——**不用默认值伪装**。
    """
    from collections import Counter
    gaps: Counter = Counter()
    prev = None
    for k in klines:
        cur = _parse_dt(k.trade_datetime)
        if cur is None:
            continue
        if prev is not None and prev.date() == cur.date():
            delta = int((cur - prev).total_seconds() // 60)
            if delta > 0:
                gaps[delta] += 1
        prev = cur
    if not gaps:
        return ''
    gap, hits = gaps.most_common(1)[0]
    total = sum(gaps.values())
    if total < 3 or hits / total < 0.8:
        return ''
    return f'{gap}m'


class MinuteKlineRepository(IMinuteKlineRepository):
    """分钟K线仓储（委托给 KlineORMRepository）"""

    def __init__(self, kline_repo=None):
        """Args: kline_repo —— 既有 KlineORMRepository 实例（缺省走 adapters.shared 单例）"""
        self._kline_repo = kline_repo

    @property
    def repo(self):
        if self._kline_repo is None:
            # 局部导入：复用进程级单例（与 DatabaseKlineProvider 同一模式）
            from adapters.shared.services import get_kline_repo
            self._kline_repo = get_kline_repo()
        return self._kline_repo

    # ------------------------------------------------------------------ 查询

    def get_minute_klines(
        self,
        symbol: str,
        start_datetime: str,
        end_datetime: str,
    ) -> List[MinuteKline]:
        """按区间查询（升序）。查询失败向上抛，不做静默空返回。"""
        df = self.repo.get_minute_klines(symbol, start_datetime, end_datetime)
        if df is None:
            raise RuntimeError(f"分钟K线查询返回 None（symbol={symbol}）")
        rows = df.to_dicts() if hasattr(df, 'to_dicts') else list(df)
        out: List[MinuteKline] = []
        for row in rows:
            dt = _parse_dt(row.get('trade_datetime'))
            if dt is None:
                continue
            out.append(MinuteKline(
                symbol=str(row.get('symbol') or symbol).split('.')[0],
                trade_datetime=dt.strftime('%Y-%m-%d %H:%M:%S'),
                open=float(row.get('open') or 0.0),
                high=float(row.get('high') or 0.0),
                low=float(row.get('low') or 0.0),
                close=float(row.get('close') or 0.0),
                volume=float(row.get('volume') or 0.0),
                amount=float(row.get('amount') or 0.0),
                period='',
                source='database_minute',
                timestamp=datetime.now().isoformat(),
            ))
        return out

    def get_latest_minute_kline(self, symbol: str) -> Optional[MinuteKline]:
        row = self.repo.get_latest_minute_kline(symbol)
        if not row:
            return None
        dt = _parse_dt(row.get('trade_datetime'))
        return MinuteKline(
            symbol=str(row.get('symbol') or symbol).split('.')[0],
            trade_datetime=dt.strftime('%Y-%m-%d %H:%M:%S') if dt else '',
            open=float(row.get('open') or 0.0),
            high=float(row.get('high') or 0.0),
            low=float(row.get('low') or 0.0),
            close=float(row.get('close') or 0.0),
            volume=float(row.get('volume') or 0.0),
            amount=float(row.get('amount') or 0.0),
            period='',
            source='database_minute',
            timestamp=datetime.now().isoformat(),
        )

    # ------------------------------------------------------------------ 写入

    def save_minute_klines(self, klines: List[MinuteKline]) -> bool:
        """批量落库（委托既有 batch_insert_minute_klines）

        注意：既有实现是 session.add_all() 直插（非 upsert），主键冲突会整批失败
        → 返回 False 并保留日志；调用方必须把 False 当失败处理（不得当作已落库）。
        """
        if not klines:
            return True
        objs = []
        for k in klines:
            dt = _parse_dt(k.trade_datetime)
            if dt is None:
                continue
            objs.append(MinuteKlineORM(
                symbol=str(k.symbol).split('.')[0],
                trade_datetime=dt,
                open=k.open,
                high=k.high,
                low=k.low,
                close=k.close,
                volume=k.volume,
                amount=k.amount,
            ))
        if not objs:
            return False
        return bool(self.repo.batch_insert_minute_klines(objs))


_repo_instance: Optional[MinuteKlineRepository] = None


def get_minute_kline_repo() -> MinuteKlineRepository:
    """进程级单例（与既有仓储模式一致）"""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = MinuteKlineRepository()
    return _repo_instance
