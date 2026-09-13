"""Qlib 数据适配器仓储（application/services/qlib/qlib_data_adapter.py 的取数出口）。

2026-09-14（REQ-24e15d）：原实现是 application/services/qlib/qlib_data_adapter.py 里
三处 pandas.read_sql(query, self.engine)，query 用 f-string 把 symbol 列表与日期值拼进 SQL
（形如 WHERE symbol IN ('600000.SH','600519.SH') AND trade_date <= '2023-12-31'）——
属"值位置注入"写法。现把三处取数收口到这里，**取值一律绑定参数**。

⚠️ 重要事实（2026-09-14 实测，写在这里避免下一个人再猜）：
    self.engine = infrastructure.persistence.database.engine.get_engine()，
    即 quantsys-v2 的**全局 Engine**，连的就是 quant_investment 这个库
    （不是另一套 schema）。但 SQL 里的表名 klines 是**不带 schema 前缀**的裸名，
    连接 search_path 实测 = "\"$user\", public"，而全库**根本没有 klines 这张表/视图**
    （pg_class where relname='klines' → 0 行；quant 下是 daily_klines，
    quant_compat 下才有 daily_klines 视图，且 quant_compat 不在 search_path 上）。
    ⇒ 这三个方法在当前库上一律报 UndefinedTable：
      · get_features → 被适配器的 try/except 吞掉，返回空 DataFrame（表现为"数据库里没有数据"）；
      · get_calendar / get_instruments → 无 try/except，异常直接向上抛。
    本轮**不修**这个既有缺陷（修它等于换表名 = 换数据源 = 改行为，须单独评估），
    只做两件事：把 SQL 收到仓储里 + 把值插值改成绑定参数。
    表名保持 klines 原样，因此迁移前后"失败/成功"的行为完全一致。
"""
from __future__ import annotations

import logging
from typing import List, Optional, Union

import pandas as pd
from sqlalchemy import bindparam, text

from infrastructure.persistence.database.engine import get_engine

logger = logging.getLogger(__name__)

__all__ = ['QlibDataRepository']

# 与旧 SQL 完全相同的取数列与顺序（下游 _convert_to_qlib_format 依赖列名）
_FEATURE_COLUMNS = "symbol, trade_date, open, high, low, close, volume, amount"


class QlibDataRepository:
    """Qlib 适配器的只读取数仓储（表名沿用旧实现的 klines）。"""

    def __init__(self):
        # 与旧实现同一个全局 Engine（同一个连接池、同一个库）
        self.engine = get_engine()

    def get_features(
        self,
        symbols: List[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        """按标的列表 + 日期窗口取 K 线原始列（返回列序与旧 SQL 一致）。

        旧 SQL（结果逐值一致，仅把插值换成绑定参数）：
            SELECT symbol, trade_date, open, high, low, close, volume, amount
            FROM klines WHERE symbol IN (<symbols 拼接>)
              [AND trade_date >= '<start_date>'] [AND trade_date <= '<end_date>']
            ORDER BY symbol, trade_date
        """
        sql = f"SELECT {_FEATURE_COLUMNS} FROM klines WHERE symbol IN :symbols"
        params: dict = {'symbols': list(symbols)}
        if start_date:
            sql += " AND trade_date >= :start_date"
            params['start_date'] = start_date
        if end_date:
            sql += " AND trade_date <= :end_date"
            params['end_date'] = end_date
        sql += " ORDER BY symbol, trade_date"

        stmt = text(sql).bindparams(bindparam('symbols', expanding=True))
        # 仍用 pandas.read_sql 取数：DataFrame 的 dtype/列序与旧实现逐位一致
        return pd.read_sql(stmt, self.engine, params=params)

    def get_calendar(
        self,
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> pd.DataFrame:
        """取区间内出现过的交易日（DISTINCT + 升序）。

        旧 SQL：
            SELECT DISTINCT trade_date FROM klines WHERE 1=1
              [AND trade_date >= '<start_time>'] [AND trade_date <= '<end_time>']
            ORDER BY trade_date
        """
        sql = "SELECT DISTINCT trade_date FROM klines WHERE 1=1"
        params: dict = {}
        if start_time:
            sql += " AND trade_date >= :start_time"
            params['start_time'] = start_time
        if end_time:
            sql += " AND trade_date <= :end_time"
            params['end_time'] = end_time
        sql += " ORDER BY trade_date"

        return pd.read_sql(text(sql), self.engine, params=params)

    def get_instruments(self) -> pd.DataFrame:
        """取全部标的（DISTINCT + 升序）。

        旧 SQL：SELECT DISTINCT symbol FROM klines ORDER BY symbol
        """
        return pd.read_sql(
            text("SELECT DISTINCT symbol FROM klines ORDER BY symbol"), self.engine
        )
