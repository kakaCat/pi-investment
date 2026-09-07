"""K线优先级同步策略

避免全市场同步（5500只）导致频繁封禁，按优先级分层同步：
- P0: 股票池内的股票（约 100-200 只）
- P1: 最近访问过的股票（热点股票）
- P2: 全市场其他股票（低优先级，可选）

2026-09-02: 创建，减少数据源压力
"""
import logging
from typing import List, Tuple, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_pool_symbols(cursor) -> Set[str]:
    """获取所有股票池中的股票代码

    Returns:
        Set[str]: 股票代码集合
    """
    cursor.execute("""
        SELECT DISTINCT unnest(symbols) AS symbol
        FROM quant.stock_pools
        WHERE pool_type IN ('static', 'dynamic')
          AND symbols IS NOT NULL
    """)
    return {row[0] for row in cursor.fetchall()}


def get_recent_accessed_symbols(cursor, days: int = 7) -> Set[str]:
    """获取最近访问过的股票（从 K 线查询日志推断）

    Args:
        days: 最近 N 天

    Returns:
        Set[str]: 股票代码集合
    """
    # 从最近的 K 线更新记录中提取
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT DISTINCT symbol
        FROM quant.daily_klines
        WHERE updated_at >= %s
        ORDER BY updated_at DESC
        LIMIT 500
    """, (cutoff_date,))

    return {row[0] for row in cursor.fetchall()}


def get_priority_sync_list(cursor, include_p2: bool = False) -> List[Tuple[str, str, int]]:
    """获取按优先级排序的同步列表

    Args:
        cursor: 数据库游标
        include_p2: 是否包含 P2（全市场其他股票）

    Returns:
        List[Tuple[symbol, name, priority]]:
        - priority: 0=P0(池内), 1=P1(热点), 2=P2(其他)
    """
    # P0: 股票池内的股票
    pool_symbols = get_pool_symbols(cursor)
    logger.info(f"P0 股票池: {len(pool_symbols)} 只")

    # P1: 最近访问过的股票
    recent_symbols = get_recent_accessed_symbols(cursor, days=7)
    logger.info(f"P1 热点股票: {len(recent_symbols)} 只")

    # 合并 P0 + P1
    high_priority_symbols = pool_symbols | recent_symbols

    # 构建优先级列表
    result = []

    # 获取所有股票信息（排除退市和 ST）
    cursor.execute("""
        SELECT symbol, name
        FROM quant.stocks
        WHERE name NOT LIKE '%退%'
          AND name NOT LIKE '%ST%'
          AND NOT is_delisted
        ORDER BY symbol
    """)

    all_stocks = cursor.fetchall()

    for symbol, name in all_stocks:
        if symbol in pool_symbols:
            priority = 0  # P0: 池内
        elif symbol in high_priority_symbols:
            priority = 1  # P1: 热点
        elif include_p2:
            priority = 2  # P2: 其他
        else:
            continue  # 不包含 P2，跳过

        result.append((symbol, name, priority))

    # 按优先级排序（P0 → P1 → P2）
    result.sort(key=lambda x: (x[2], x[0]))

    return result


def build_priority_query(scope: str, specific_symbols=None, priority_levels=None):
    """构建按优先级的选股 SQL

    Args:
        scope: 'priority' 按优先级 | 'all' 全市场（保留兼容）
        specific_symbols: 指定股票列表
        priority_levels: 优先级列表，如 [0, 1] 表示只同步 P0+P1

    Returns:
        (sql, params) 元组
    """
    if specific_symbols:
        placeholders = ','.join(['%s'] * len(specific_symbols))
        return (
            f"""
                SELECT symbol, name
                FROM quant.stocks
                WHERE symbol IN ({placeholders})
                ORDER BY symbol
            """,
            list(specific_symbols),
        )

    if scope == 'priority':
        # 按优先级同步：P0(池内) + P1(热点) + [可选]P2(全市场)
        # 使用 CTE 构建优先级标记
        if priority_levels is None:
            priority_levels = [0, 1]  # 默认只同步 P0+P1

        priority_list = ','.join(map(str, priority_levels))

        return (
            f"""
                WITH pool_symbols AS (
                    SELECT DISTINCT unnest(symbols) AS symbol
                    FROM quant.stock_pools
                    WHERE pool_type IN ('static', 'dynamic')
                      AND symbols IS NOT NULL
                ),
                recent_symbols AS (
                    SELECT DISTINCT symbol
                    FROM quant.daily_klines
                    WHERE updated_at >= NOW() - INTERVAL '7 days'
                    ORDER BY updated_at DESC
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
                    WHERE s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                )
                SELECT symbol, name
                FROM prioritized_stocks
                WHERE priority IN ({priority_list})
                ORDER BY priority, symbol
            """,
            None,
        )

    # 兼容旧的 'all' 模式（全市场按陈旧度排序）
    return (
        """
            SELECT s.symbol, s.name
            FROM quant.stocks s
            LEFT JOIN (
                SELECT symbol, MAX(trade_date) AS max_date
                FROM quant.daily_klines
                GROUP BY symbol
            ) k ON k.symbol = s.symbol
            WHERE s.name NOT LIKE '%退%'
              AND s.name NOT LIKE '%ST%'
              AND NOT s.is_delisted
            ORDER BY k.max_date ASC NULLS FIRST, s.symbol
        """,
        None,
    )
