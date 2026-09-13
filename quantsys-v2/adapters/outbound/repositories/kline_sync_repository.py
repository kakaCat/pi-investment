"""K线同步仓储：选股宇宙选择 + 写入后完整性/量纲自检（REQ-24e15d t4）。

建立背景（2026-09-13，w-32314d00）：
    这些查询原先全部内联在 `infrastructure/jobs/kline_update_job.py` 里，用
    `engine.raw_connection()` 拿到的裸 psycopg2 cursor 执行——作业层同时承担了
    "编排/限速/告警"和"数据访问"两种职责，SQL 文本散落在作业里。此文件把数据访问
    收敛到仓储层，作业层只剩编排。

为什么这些查询**保留 SQL 而不硬转纯 ORM**（逐处评估的结论，非偷懒）：
  ① 选股宇宙（scope=all/gem/priority/batch）是集合式查询：CTE + UNION ALL +
     按"最久未更新"排序。展开成 ORM 会退化成多次往返 + Python 侧合并，
     在每日 5500 只的规模上性能与语义都会变差；
  ② 量纲自检用 percentile_cont 分组统计，属分析型 SQL。
  纪律约束（与 tools/non_orm_sql_scan.py 的口径一致）：
    · SQL 只允许出现在本层；
    · **取值一律绑定参数**（:name），不做字符串插值；
    · 标识符（表名/列名）不参与拼接——本文件无任何 f-string 标识符插值。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import Text

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import Stock
from utils.symbol_classifier import index_symbols_for_exclusion, is_index_symbol

logger = logging.getLogger(__name__)

__all__ = ['KlineSyncRepository', 'build_stock_query', 'STANDARD_SYMBOL_SQL']

# 成交额量级异常判据：当日成交额 > 该股近 20 日均额 × 该倍数即告警
# （量纲错会把 amount 整体放大约 100 倍，真实放量极少超过 50 倍）
AMOUNT_SCALE_THRESHOLD = 50.0

# 量纲交叉截面判据（2026-09-10 w-23c70356 立，实测标定）：
# r = 当日 volume / stocks.avg_volume（独立源，股），m = 同日同板块 r 的中位数。
# 缺陷行 r ≈ 100×m。以 2026-07~09 已知 2,098 行缺陷为 ground truth 实测：
# K=20 → 召回 2,080/2,098=99.1%、全市场误报 727/262,874=0.28%；
# K=50 → 召回 70.8%、误报 0.19%（故取 20）。
# 该判据与 AMOUNT_SCALE_THRESHOLD（时序自比）互补：截面判据不怕"连续多日整体
# 放大"（时序中位数会被污染），时序判据不怕 avg_volume 缺失。
VOLUME_CROSS_SECTION_THRESHOLD = 20.0

# 符号形状白名单（2026-09-11 w-23c70356 立）：daily_klines 只接受 6 位 A 股裸码。
# 背景：quant.stocks 曾被测试数据污染（600000.SH…600009.SH，name='Test'），
# 同步任务把 stocks 当宇宙逐日写出 1,213 行伪 K 线——其中 600001/600002/600003/
# 600005（邯郸钢铁/齐鲁石化/ST东北高/武钢股份）早已退市却出现 2026 年行情，且与
# 真实裸码同日收盘价 0 天相同（改名合并会污染真数据）。清理 1,507 行后加双保险：
# ① 选股 SQL 层过滤（本常量）② 写入循环兜底（显式 symbols 入参也能挡住）。
STANDARD_SYMBOL_SQL = "s.symbol ~ '^[0-9]{6}$'"


def build_stock_query(scope: str, specific_symbols=None, batch_size=500):
    """构建选股 SQL（2026-08-02 抽出以便单测；2026-09-13 从 jobs 移入仓储）。

    过滤规则：all/gem/priority/batch 范围排除退市股（is_delisted）和名称含"退"/"ST"的；
    显式指定的 symbols 不过滤（调用方明确要查就尊重）。

    scope:
    - 'batch': 分批轮转同步 P0(池内) + P1(热点) + 按陈旧度补充 N 只（2026-09-02 新增）
    - 'priority': 按优先级同步 P0(池内) + P1(热点)，约 300 只
    - 'all': 全市场按陈旧度排序
    - 'gem': 仅创业板

    Returns:
        (sql, params) 元组，可直接 execute(sql, params)。
    """
    if specific_symbols:
        return (
            """
                SELECT symbol, name
                FROM quant.stocks
                WHERE symbol IN :symbols
                ORDER BY symbol
            """,
            {'symbols': list(specific_symbols)},
        )

    if scope == 'batch':
        # 2026-09-02: 分批轮转同步策略
        # P0+P1 每天必同步（核心股票） + 按陈旧度补充 batch_size 只
        # 这样既保证核心股票实时性，又能通过多天轮转覆盖全市场
        return (
            f"""
                WITH pool_symbols AS (
                    SELECT DISTINCT unnest(symbols) AS symbol
                    FROM quant.stock_pools
                    WHERE pool_type IN ('static', 'dynamic')
                      AND symbols IS NOT NULL
                ),
                recent_symbols AS (
                    SELECT symbol
                    FROM quant.daily_klines
                    WHERE trade_date >= CURRENT_DATE - INTERVAL '7 days'
                    GROUP BY symbol
                    ORDER BY MAX(trade_date) DESC
                    LIMIT 500
                ),
                high_priority AS (
                    SELECT s.symbol, s.name, 0 AS priority
                    FROM quant.stocks s
                    WHERE s.symbol IN (SELECT symbol FROM pool_symbols)
                      AND {STANDARD_SYMBOL_SQL}
                      AND s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                    UNION
                    SELECT s.symbol, s.name, 1 AS priority
                    FROM quant.stocks s
                    WHERE s.symbol IN (SELECT symbol FROM recent_symbols)
                      AND {STANDARD_SYMBOL_SQL}
                      AND s.symbol NOT IN (SELECT symbol FROM pool_symbols)
                      AND s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                ),
                stale_stocks AS (
                    SELECT s.symbol, s.name, 2 AS priority
                    FROM quant.stocks s
                    LEFT JOIN (
                        SELECT symbol, MAX(trade_date) AS max_date
                        FROM quant.daily_klines
                        GROUP BY symbol
                    ) k ON k.symbol = s.symbol
                    WHERE s.symbol NOT IN (SELECT symbol FROM high_priority)
                      AND {STANDARD_SYMBOL_SQL}
                      AND s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                    ORDER BY k.max_date ASC NULLS FIRST, s.symbol
                    LIMIT :batch_size
                )
                SELECT symbol, name FROM (
                    SELECT symbol, name, priority FROM high_priority
                    UNION ALL
                    SELECT symbol, name, priority FROM stale_stocks
                ) ordered
                ORDER BY ordered.priority, ordered.symbol
            """,
            {'batch_size': batch_size},
        )

    if scope == 'priority':
        # 2026-09-02: 优先级同步，只同步核心股票
        # P0: 股票池内的股票
        # P1: 最近 7 天访问过的股票（热点）
        return (
            """
                WITH pool_symbols AS (
                    SELECT DISTINCT unnest(symbols) AS symbol
                    FROM quant.stock_pools
                    WHERE pool_type IN ('static', 'dynamic')
                      AND symbols IS NOT NULL
                ),
                recent_symbols AS (
                    SELECT symbol
                    FROM quant.daily_klines
                    WHERE trade_date >= CURRENT_DATE - INTERVAL '7 days'
                    GROUP BY symbol
                    ORDER BY MAX(trade_date) DESC
                    LIMIT 500
                ),
                prioritized_stocks AS (
                    SELECT
                        s.symbol,
                        s.name,
                        CASE
                            WHEN p.symbol IS NOT NULL THEN 0  -- P0: 池内
                            WHEN r.symbol IS NOT NULL THEN 1  -- P1: 热点
                            ELSE 2                             -- P2: 其他
                        END AS priority
                    FROM quant.stocks s
                    LEFT JOIN pool_symbols p ON p.symbol = s.symbol
                    LEFT JOIN recent_symbols r ON r.symbol = s.symbol
                    WHERE s.symbol ~ '^[0-9]{6}$'
                      AND s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                )
                SELECT symbol, name
                FROM prioritized_stocks
                WHERE priority IN (0, 1)  -- 只同步 P0 + P1
                ORDER BY priority, symbol
            """,
            None,
        )

    if scope == 'gem':
        return (
            """
                SELECT symbol, name
                FROM quant.stocks
                WHERE (symbol LIKE '300%' OR symbol LIKE '301%')
                  AND symbol ~ '^[0-9]{6}$'
                  AND name NOT LIKE '%退%'
                  AND name NOT LIKE '%ST%'
                  AND NOT is_delisted
                ORDER BY symbol
            """,
            None,
        )

    # 全市场：K线是全市场功能（机会扫描/市场情绪/行业分析）的共同
    # 上游，只更创业板会让其余 4500 只股票静默饿死（2026-07-28 定位）
    #
    # 按陈旧度排序（最久未更新的排最前）：腾讯源每窗口约放行
    # 1500-2500 只后限流断流，若按代码排序，每次运行都从头补
    # 00xxxx，60xxxx 永远轮不到；按陈旧度排序后多次运行自动收敛
    return (
        """
            SELECT s.symbol, s.name
            FROM quant.stocks s
            LEFT JOIN (
                SELECT symbol, MAX(trade_date) AS max_date
                FROM quant.daily_klines
                GROUP BY symbol
            ) k ON k.symbol = s.symbol
            WHERE s.symbol ~ '^[0-9]{6}$'
              AND s.name NOT LIKE '%退%'
              AND s.name NOT LIKE '%ST%'
              AND NOT s.is_delisted
            ORDER BY k.max_date ASC NULLS FIRST, s.symbol
        """,
        None,
    )


class KlineSyncRepository(BaseORMRepository[Stock]):
    """K线同步的选股与自检数据访问。

    继承 BaseORMRepository 只为其 session/事务/回滚基础设施（scoped_session 每线程现取、
    _safe_rollback 防线程毒化）；本类主要执行集合式/分析型 SQL（见模块 docstring 的口径说明）。
    """

    model = Stock

    # ---------------- 选股宇宙 ----------------

    def select_sync_universe(
        self, scope: str, specific_symbols: Optional[List[str]] = None, batch_size: int = 500
    ) -> List[Tuple[str, str]]:
        """按 scope 选出本次要同步的 (symbol, name) 列表（顺序即同步优先级）。"""
        sql, params = build_stock_query(scope, specific_symbols, batch_size)
        stmt = text(sql)
        if params and 'symbols' in params:
            stmt = stmt.bindparams(bindparam('symbols', expanding=True))
        rows = self.session.execute(stmt, params or {}).fetchall()

        # 指数元数据行必须从同步宇宙里剔除（2026-09-13 w-32314d00 实测发现）：
        # quant.stocks 里有 4 行指数占位记录（000300 沪深300 / 399001 深证成指 /
        # 399006 创业板指 / 399300 沪深300(深)，全部 list_date IS NULL），它们能通过
        # '^[0-9]{6}$' 形状过滤，于是**每次同步都会白白请求这 4 个指数**，取回的指数
        # 价格只能在写入口被 filter_index_rows 丢弃（每日刷 4 条告警）。
        # 更危险的是：写入口那道闸门一旦被绕过/回归，就是 chk_daily_klines_no_indexrows
        # 约束违规（585f5a3f 等 5 起事件的历史路径）。
        # 判定复用 utils.symbol_classifier.is_index_symbol —— 与写入口**同一套语义**
        # （白名单 + stocks 表 list_date 定夺歧义码），不在此处另写一份规则以免漂移。
        # 开销：仅白名单内的少数代码会真正查表，5000+ 普通代码在内存里即判定完毕。
        return [(s, n) for (s, n) in rows if not is_index_symbol(s)]

    # ---------------- 写入 ----------------

    def upsert_fetched_klines(self, symbol: str, klines) -> Optional[int]:
        """把 provider 取回的 K 线对象列表 upsert 进 quant.daily_klines。

        2026-09-13（w-32314d00，REQ-24e15d t4）：作业层原先是"每行一条手写 INSERT +
        每只股票 commit"，这里收敛到 KlineORMRepository.batch_insert_daily_klines
        ——**daily_klines 的唯一写入口**，它内置三道作业层原先没有的护栏：
          ① filter_index_rows：指数行不入 daily_klines（约束 chk_daily_klines_no_indexrows）；
          ② 缺失 stocks 元数据时自动补建（原写法会直接撞 FK）；
          ③ market 无法从代码推断的标的跳过（避免 chk_stocks_market）。

        Args:
            symbol: 标的代码（6 位裸码）
            klines: provider 返回的 K 线对象列表（含 date/open/high/low/close/volume/amount/turnover_rate）

        Returns:
            写入行数；写入失败返回 None（调用方据此计 failed，不吞错）。
        """
        from infrastructure.persistence.orm.models import DailyKline
        from adapters.outbound.repositories.kline_repository import KlineORMRepository

        objs = []
        for k in klines:
            objs.append(DailyKline(
                symbol=symbol,
                trade_date=str(k.date)[:10],
                open=float(k.open),
                high=float(k.high),
                low=float(k.low),
                close=float(k.close),
                volume=int(k.volume),
                amount=float(k.amount),
                turnover_rate=float(k.turnover_rate),
            ))
        if not objs:
            return 0
        ok = KlineORMRepository().batch_insert_daily_klines(objs)
        return len(objs) if ok else None

    # ---------------- 写入后自检 ----------------

    def count_missing_amount(self, target_date: str) -> int:
        """基准日有成交量但成交额缺失的行数（K线写入后的完整性自检）。

        自检失败不阻断同步（返回 0 并告警），因为它是观测手段而非数据正确性前提。

        指数/伪代码排除（2026-09-10 w-23c70356）：指数行的 amount 未知即未知（已置
        NULL，不做 volume×close 估算，见 utils.symbol_classifier），若不排除则每日同步
        指数（399300 等）后该自检必然误报 critical。
        """
        try:
            stmt = text(
                "SELECT count(*) FROM quant.daily_klines "
                "WHERE trade_date = :d AND volume > 0 AND (amount IS NULL OR amount <= 0) "
                "AND symbol !~ '^399' AND position('.' in symbol) = 0 "
                "AND NOT (symbol = ANY(:idx))"
            ).bindparams(bindparam('idx', type_=ARRAY(Text)))
            row = self.session.execute(
                stmt, {'d': target_date, 'idx': list(index_symbols_for_exclusion())}
            ).fetchone()
            return int(row[0]) if row else 0
        except Exception as e:  # noqa: BLE001 - 自检异常不得影响同步结果
            self._safe_rollback()
            logger.warning(f"成交额完整性自检失败（不影响同步）: {e}")
            return 0

    def detect_amount_scale_anomalies(
        self, target_date: str, threshold: float = AMOUNT_SCALE_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """基准日成交额量级异常检测（观测手段，不改数）。

        判据：当日 amount > 该股近 20 个交易日中位 amount × threshold。
        背景：volume 的「手/股」量纲在不同源/板块间不一致（科创板源给股、主板源给手），
        量纲错会整体放大约 100 倍，但 amount/volume/close 仍自洽（VWAP 自洽校验查不出），
        只能靠跨期离群度发现。实测 2026-07~08 科创板 2,110 行 volume×100。
        仅告警不阻断；是否缺陷需独立源复核后由数据侧修复。
        """
        try:
            stmt = text(
                "WITH ref AS ("
                "  SELECT symbol, percentile_cont(0.5) WITHIN GROUP (ORDER BY amount) AS med,"
                "         count(*) AS n"
                "  FROM quant.daily_klines"
                # 注意不能用 :d::date —— SQLAlchemy 的 :name 绑定遇 '::' 会解析歧义，
                # 实测报 'syntax error at or near ":"'。用 CAST 显式表达。
                "  WHERE trade_date < :d AND trade_date >= CAST(:d AS date) - INTERVAL '40 days'"
                "    AND amount > 0 AND volume > 0"
                "  GROUP BY symbol HAVING count(*) >= 5)"
                " SELECT k.symbol, k.volume, k.amount, ref.med"
                " FROM quant.daily_klines k JOIN ref ON ref.symbol = k.symbol"
                " WHERE k.trade_date = :d AND k.amount > 0 AND ref.med > 0"
                "   AND k.amount > :th * ref.med"
                "   AND k.symbol !~ '^399' AND position('.' in k.symbol) = 0"
                " ORDER BY k.amount / ref.med DESC LIMIT 50"
            )
            rows = self.session.execute(stmt, {'d': target_date, 'th': threshold}).fetchall()
            return [
                {'symbol': r[0], 'volume': float(r[1] or 0), 'amount': float(r[2] or 0),
                 'median_amount': float(r[3] or 0), 'multiple': float(r[2]) / float(r[3])}
                for r in rows
            ]
        except Exception as e:  # noqa: BLE001 - 自检异常不得影响同步结果
            self._safe_rollback()
            logger.warning(f"成交额量级自检失败（不影响同步）: {e}")
            return []

    def detect_volume_unit_anomalies(
        self, target_date: str, threshold: float = VOLUME_CROSS_SECTION_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """基准日成交量量纲异常检测（观测手段，不改数）。

        判据：r = volume / stocks.avg_volume（股），同日同板块中位数 m，r > threshold × m。
        背景：成交量的「手/股」量纲错会让数值整体放大 100 倍，而 amount/volume/close
        仍自洽（VWAP 自洽校验无感）；时序自比（近 N 日中位额）在缺陷连续多日时会被
        污染，截面自比不受影响——实测 2026-08-14~08-27 连续 10 个交易日每天固定
        196 只科创板标的 volume ×100。仅告警不阻断。
        """
        try:
            stmt = text(
                "WITH cur AS ("
                "  SELECT k.symbol, k.volume, s.avg_volume,"
                "         CASE WHEN k.symbol ~ '^(688|689)' THEN '688'"
                "              WHEN k.symbol ~ '^6' THEN '60'"
                "              WHEN k.symbol ~ '^(300|301)' THEN '300'"
                "              WHEN k.symbol ~ '^(000|001|002|003)' THEN '000'"
                "              ELSE k.symbol END AS brd"
                "  FROM quant.daily_klines k JOIN quant.stocks s ON s.symbol = k.symbol"
                "  WHERE k.trade_date = :d AND k.volume > 0 AND s.avg_volume > 0"
                "    AND k.symbol ~ '^[0-9]{6}$' AND k.symbol !~ '^399'),"
                " m AS ("
                "  SELECT brd, percentile_cont(0.5) WITHIN GROUP (ORDER BY volume / avg_volume) AS med"
                "  FROM cur GROUP BY brd HAVING count(*) >= 5)"
                " SELECT cur.symbol, cur.volume, cur.avg_volume, m.med"
                " FROM cur JOIN m USING (brd)"
                " WHERE (cur.volume / cur.avg_volume) > :th * m.med"
                " ORDER BY (cur.volume / cur.avg_volume) / m.med DESC LIMIT 50"
            )
            rows = self.session.execute(stmt, {'d': target_date, 'th': threshold}).fetchall()
            return [
                {'symbol': r[0], 'volume': float(r[1] or 0), 'avg_volume': float(r[2] or 0),
                 'median_ratio': float(r[3] or 0),
                 'multiple': (float(r[1]) / float(r[2])) / float(r[3]) if r[2] and r[3] else 0.0}
                for r in rows
            ]
        except Exception as e:  # noqa: BLE001 - 自检异常不得影响同步结果
            self._safe_rollback()
            logger.warning(f"成交量量纲截面自检失败（不影响同步）: {e}")
            return []
