"""
K线数据更新Job - 使用多数据源自动更新

每日自动更新K线数据，支持多数据源fallback（tencent → akshare）

scope:
- all: 全市场（默认）。K线是全市场功能（机会扫描/市场情绪/行业分析）的
  共同上游——只更创业板会让其余 4500 只股票静默饿死（2026-07-28 定位：
  07-22 后全市场日更覆盖率从 1351 只逐日衰减到 1 只）
- gem: 仅创业板（旧行为，保留兼容）
"""
import os
import sys
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径

from adapters.outbound.datasources.manager import DataProviderManager
from infrastructure.persistence.database.engine import get_engine
from utils.symbol_classifier import index_symbols_for_exclusion

# 成交额量级异常判据：当日成交额 > 该股近 20 日均额 × 该倍数即告警
# （量纲错会把 amount 整体放大约 100 倍，真实放量极少超过 50 倍）
AMOUNT_SCALE_THRESHOLD = 50.0

logger = logging.getLogger(__name__)


def build_stock_query(scope: str, specific_symbols=None, batch_size=500):
    """构建选股 SQL（抽出以便单测，2026-08-02）。

    过滤规则：all/gem/priority/batch 范围排除退市股（is_delisted）和名称含"退"/"ST"的；
    显式指定的 symbols 不过滤（调用方明确要查就尊重）。

    scope:
    - 'batch': 分批轮转同步 P0(池内) + P1(热点) + 按陈旧度补充 N 只（2026-09-02 新增）
    - 'priority': 按优先级同步 P0(池内) + P1(热点)，约 300 只
    - 'all': 全市场按陈旧度排序
    - 'gem': 仅创业板

    Args:
        batch_size: scope='batch' 时，除 P0+P1 外补充的最旧股票数量

    Returns:
        (sql, params) 元组，可直接 cursor.execute(sql, params)。
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
                      AND s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                    UNION
                    SELECT s.symbol, s.name, 1 AS priority
                    FROM quant.stocks s
                    WHERE s.symbol IN (SELECT symbol FROM recent_symbols)
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
                      AND s.name NOT LIKE '%退%'
                      AND s.name NOT LIKE '%ST%'
                      AND NOT s.is_delisted
                    ORDER BY k.max_date ASC NULLS FIRST, s.symbol
                    LIMIT {batch_size}
                )
                SELECT symbol, name FROM (
                    SELECT symbol, name, priority FROM high_priority
                    UNION ALL
                    SELECT symbol, name, priority FROM stale_stocks
                ) ordered
                ORDER BY ordered.priority, ordered.symbol
            """,
            None,
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
                    WHERE s.name NOT LIKE '%退%'
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
            WHERE s.name NOT LIKE '%退%'
              AND s.name NOT LIKE '%ST%'
              AND NOT s.is_delisted
            ORDER BY k.max_date ASC NULLS FIRST, s.symbol
        """,
        None,
    )


def update_gem_klines(**params):
    """
    更新K线数据

    Args:
        **params: 任务参数
            - days: 更新最近N天的数据（默认5天）
            - symbols: 指定股票代码列表（可选）
            - scope: 同步范围（2026-09-02 更新）
              * 'batch': 分批轮转（P0+P1 必同步 + 按陈旧度补充 batch_size 只）
              * 'priority': 仅核心股票（P0+P1，约 300 只）
              * 'all': 全市场按陈旧度排序（约 5500 只）
              * 'gem': 仅创业板
            - batch_size: scope='batch' 时，除 P0+P1 外补充的最旧股票数量（默认 500）
            - interval_seconds: 每只股票请求间隔秒数区间 (low, high)，
              默认 (0.3, 0.8) 随机抖动（防 WAF 封禁——2026-07-28 实测
              间隔 0.05s 跑约770只后被断流；连空 50 只会自适应休眠 30s）。
              interval_seconds=0 关闭（测试/小批量用）
            - pause: （已废弃别名）等价于 interval_seconds=(pause, pause)

    Returns:
        dict: 执行结果
    """
    scope = params.get('scope', 'all')
    batch_size = params.get('batch_size', 500)

    logger.info("="*70)
    logger.info(f"K线数据更新任务开始 (scope={scope}, batch_size={batch_size if scope == 'batch' else 'N/A'})")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)

    days = params.get('days', 5)
    specific_symbols = params.get('symbols', None)
    # 请求限速：每只股票之间的间隔秒数区间（防 WAF 封禁，2026-07-28）
    # interval_seconds=0 关闭（测试/小批量用）；pause 为废弃别名
    pause = params.get('pause', None)
    default_interval = (0.3, 0.8) if pause is None else (float(pause), float(pause))
    interval = params.get('interval_seconds', default_interval)

    engine = None
    conn = None

    try:
        # 初始化
        engine = get_engine()
        conn = engine.raw_connection()
        cursor = conn.cursor()

        # 获取股票列表（选股 SQL 已抽出为 build_stock_query，含退市过滤）
        # 注意：SQL 内含 LIKE '%退%'，params 为 None 时必须单参调用，
        # 否则 psycopg2 会把 % 当占位符插值报 IndexError
        sql, query_params = build_stock_query(scope, specific_symbols, batch_size)
        if query_params:
            cursor.execute(sql, query_params)
        else:
            cursor.execute(sql)

        stocks = cursor.fetchall()
        total = len(stocks)
        logger.info(f"需要更新: {total}只股票")

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"日期范围: {start_date} -> {end_date}")

        # stale 校验的基准日：最近一个"应当已有 EOD 数据"的交易日。
        # 盘中/早盘/非交易日跑任务时，当天本来就没有日K，不能拿今天当
        # 基准（否则全部误报 stale，2026-07-31 回填时 4364 只全误报）。
        # 规则：工作日且已过 15:00 → 今天；否则 → 上一个工作日。
        # （无交易日历，节假日会稍偏保守，仅影响 stale 计数不影响入库）
        now = datetime.now()
        target_date = end_date
        if now.weekday() >= 5 or now.hour < 15:
            d = now - timedelta(days=1)
            while d.weekday() >= 5:
                d -= timedelta(days=1)
            target_date = d.strftime('%Y-%m-%d')

        # 初始化数据源管理器
        manager = DataProviderManager()

        success = 0
        failed = 0
        skipped = 0
        stale = 0  # 数据有效但未覆盖到目标日期（如 baostock 当日 EOD 未发布）
        consecutive_empty = 0

        for i, (symbol, name) in enumerate(stocks, 1):
            # 限速：首只之前不 sleep
            if i > 1 and interval and interval[1] > 0:
                time.sleep(random.uniform(*interval))
            try:
                # 使用多数据源获取数据（自动fallback：tencent → akshare）
                # 注意：manager.get_klines 返回 {'success', 'data', 'source'} 字典，
                # data 是 KlineData 对象列表，不是 DataFrame（2026-07-23 修复
                # "'dict' object has no attribute 'iterrows'" 契约错位）
                result = manager.get_klines(
                    symbol,
                    'daily',
                    start_date,
                    end_date,
                )
                klines = result.get('data') if result.get('success') else None

                if not klines:
                    skipped += 1
                    consecutive_empty += 1
                    if consecutive_empty >= 50:
                        # 数据源大概率被限流，休眠冷却后重试这批
                        logger.warning(
                            f"连续 {consecutive_empty} 只无数据，疑似数据源限流，休眠 30s")
                        time.sleep(30)
                        consecutive_empty = 0
                    logger.debug(f"[{i}/{total}] {symbol} - 无数据")
                    continue

                consecutive_empty = 0

                # 插入数据库
                inserted = 0
                for k in klines:
                    cursor.execute("""
                        INSERT INTO quant.daily_klines
                        (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, trade_date)
                        DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            amount = EXCLUDED.amount,
                            turnover_rate = EXCLUDED.turnover_rate
                    """, (
                        symbol,
                        k.date,
                        float(k.open),
                        float(k.high),
                        float(k.low),
                        float(k.close),
                        int(k.volume),
                        float(k.amount),
                        float(k.turnover_rate),
                    ))
                    inserted += 1

                conn.commit()

                # 目标日期校验：数据有效但只到更早日期时（如 baostock 当日
                # EOD 尚未发布），仍入库但计为 stale 而非 success——避免
                # 07-29 式假成功（报"成功5268只"实际仅355只有当日数据）。
                # 基准是 target_date（最近已收盘交易日），不是 end_date
                latest_date = max(str(k.date)[:10] for k in klines)
                if latest_date < target_date:
                    stale += 1
                    if stale <= 5 or stale % 500 == 0:
                        logger.warning(
                            f"[{i}/{total}] {symbol} - 数据仅到 {latest_date}，"
                            f"未覆盖基准日 {target_date}")
                else:
                    success += 1

                if i % 200 == 0:
                    logger.info(f"进度: [{i}/{total}] 成功{success} 失败{failed} 跳过{skipped}")

            except Exception as e:
                failed += 1
                logger.warning(f"[{i}/{total}] {symbol} - 失败: {str(e)[:50]}")
                conn.rollback()

        cursor.close()

        # 封禁/故障降级检测：样本足够且成功率过低时标记（2026-07-28）
        processed = success + failed + skipped + stale
        provider_health = 'ok'
        if processed >= 20 and success < processed * 0.5:
            provider_health = 'degraded'
            logger.critical(
                f"⚠️ K线数据源疑似被封/故障: {processed}只仅{success}只成功，"
                f"请检查 provider 状态（WAF/IP封禁）")

        # 陈旧数据预警：大量股票未覆盖基准日（通常意味着首选源当日
        # EOD 未发布，需要晚些补跑），不算任务失败但必须可见（2026-07-30）
        if stale > 0:
            logger.warning(
                f"⚠️ {stale}只股票数据未覆盖基准日 {target_date}"
                f"（上游 EOD 未发布），建议稍后补跑")

        # 成交额完整性自检（2026-09-10 立）：本 INSERT 是 daily_klines 的唯一
        # 写入路径（原样落 float(k.amount)），上游 provider 不返回 amount 时会
        # 静默写 0——新浪日线接口只有 volume 无 amount，2026-09-02 起其成为主源
        # 后全库累积 185 万行 amount=0/NULL。在此对本次同步覆盖的基准日做一次
        # 自检，让"成交额丢失"在写入当日就可见，而不是几周后在因子/回测层发现。
        amount_missing = _count_missing_amount(conn, target_date)
        if amount_missing:
            logger.critical(
                f"⚠️ {target_date} 有 {amount_missing} 行有成交量但 amount 为 0/NULL "
                f"——数据源未提供成交额，请核查 provider 的 KlineData.amount 契约")

        # 成交额量级异常自检（2026-09-10 w-23c70356 立）：量纲（手/股）错误不破坏
        # amount/volume/close 自洽性，既有 VWAP 自洽校验看不见，只能按"当日额 vs
        # 自身近期中位额"的离群度发现。实测 2026-07~08 科创板 2,110 行 volume 被
        # 放大 100 倍（688008 单日 14,881 亿元）、指数伪行 949 万亿元。
        amount_scale_anomalies = _detect_amount_scale_anomalies(conn, target_date)
        if amount_scale_anomalies:
            top = ", ".join(f"{a['symbol']} ×{a['multiple']:.0f}" for a in amount_scale_anomalies[:5])
            logger.critical(
                f"⚠️ {target_date} 有 {len(amount_scale_anomalies)} 行成交额超该股近期中位额 "
                f"{AMOUNT_SCALE_THRESHOLD:.0f} 倍，疑似量纲（手/股）错误或极端放量，需独立源复核: {top}")

        result = {
            'action': 'kline_update',
            'status': 'success',
            'scope': scope,
            'timestamp': datetime.now().isoformat(),
            'provider_health': provider_health,
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'stale': stale,
            'amount_missing': amount_missing,
            'amount_scale_anomalies': amount_scale_anomalies[:20],
            'date_range': f"{start_date} -> {end_date}",
            'target_date': target_date,
            'message': f'K线更新完成: 成功{success}只, 失败{failed}只, 跳过{skipped}只, 未覆盖基准日{stale}只'
        }

        logger.info("="*70)
        logger.info(f"✅ K线更新完成 (scope={scope})")
        logger.info(f"  成功: {success}只")
        logger.info(f"  失败: {failed}只")
        logger.info(f"  跳过: {skipped}只")
        logger.info(f"  未覆盖基准日({target_date}): {stale}只")
        logger.info(f"  成交额缺失(volume>0 且 amount<=0): {amount_missing} 行")
        logger.info(f"  成交额量级异常(>{AMOUNT_SCALE_THRESHOLD:.0f}×近期中位): {len(amount_scale_anomalies)} 行")
        logger.info("="*70)

        return result

    except Exception as e:
        logger.error(f"❌ K线更新失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            'action': 'kline_update',
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'message': 'K线更新失败'
        }

    finally:
        if conn:
            conn.close()


# Job注册点 - scheduler会调用这个函数
def _count_missing_amount(conn, target_date: str) -> int:
    """基准日有成交量但成交额缺失的行数（K线写入后的完整性自检）。

    自检失败不阻断同步（返回 0 并告警），因为它是观测手段而非数据正确性前提。

    指数/伪代码排除（2026-09-10 w-23c70356）：指数行的 amount 未知即未知（已置
    NULL，不做 volume×close 估算，见 utils.symbol_classifier），若不排除则每日同步
    指数（399300 等）后该自检必然误报 critical。
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM quant.daily_klines "
                "WHERE trade_date = %s AND volume > 0 AND (amount IS NULL OR amount <= 0) "
                "AND symbol !~ '^399' AND position('.' in symbol) = 0 "
                "AND NOT (symbol = ANY(%s))",
                (target_date, list(index_symbols_for_exclusion())),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception as e:  # noqa: BLE001 - 自检异常不得影响同步结果
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning(f"成交额完整性自检失败（不影响同步）: {e}")
        return 0


def _detect_amount_scale_anomalies(conn, target_date: str, threshold: float = AMOUNT_SCALE_THRESHOLD) -> list:
    """基准日成交额量级异常检测（观测手段，不改数）。

    判据：当日 amount > 该股近 20 个交易日中位 amount × threshold。
    背景：volume 的「手/股」量纲在不同源/板块间不一致（科创板源给股、主板源给手），
    量纲错会整体放大约 100 倍，但 amount/volume/close 仍自洽（VWAP 自洽校验查不出），
    只能靠跨期离群度发现。实测 2026-07~08 科创板 2,110 行 volume×100。
    仅告警不阻断；是否缺陷需独立源复核后由数据侧修复。
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "WITH ref AS ("
                "  SELECT symbol, percentile_cont(0.5) WITHIN GROUP (ORDER BY amount) AS med, count(*) AS n"
                "  FROM quant.daily_klines"
                "  WHERE trade_date < %s AND trade_date >= %s::date - INTERVAL '40 days'"
                "    AND amount > 0 AND volume > 0"
                "  GROUP BY symbol HAVING count(*) >= 5)"
                " SELECT k.symbol, k.volume, k.amount, ref.med"
                " FROM quant.daily_klines k JOIN ref ON ref.symbol = k.symbol"
                " WHERE k.trade_date = %s AND k.amount > 0 AND ref.med > 0"
                "   AND k.amount > %s * ref.med"
                "   AND k.symbol !~ '^399' AND position('.' in k.symbol) = 0"
                " ORDER BY k.amount / ref.med DESC LIMIT 50",
                (target_date, target_date, target_date, threshold),
            )
            return [
                {'symbol': r[0], 'volume': float(r[1] or 0), 'amount': float(r[2] or 0),
                 'median_amount': float(r[3] or 0), 'multiple': float(r[2]) / float(r[3])}
                for r in cur.fetchall()
            ]
    except Exception as e:  # noqa: BLE001 - 自检异常不得影响同步结果
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning(f"成交额量级自检失败（不影响同步）: {e}")
        return []


def execute(**params):
    """Scheduler调用的入口函数"""
    return update_gem_klines(**params)


if __name__ == '__main__':
    # 测试执行
    result = update_gem_klines(days=5)
    print(f"\n执行结果: {result}")
