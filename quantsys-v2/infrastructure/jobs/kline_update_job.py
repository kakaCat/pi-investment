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
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径

from adapters.outbound.datasources.manager import DataProviderManager
from infrastructure.persistence.database.engine import get_engine

logger = logging.getLogger(__name__)


def build_stock_query(scope: str, specific_symbols=None):
    """构建选股 SQL（抽出以便单测，2026-08-02）。

    过滤规则：all/gem 范围排除退市股（is_delisted）和名称含"退"/"ST"的；
    显式指定的 symbols 不过滤（调用方明确要查就尊重）。

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
            - scope: 'all' 全市场（默认）| 'gem' 仅创业板
            - interval_seconds: 每只股票请求间隔秒数区间 (low, high)，
              默认 (0.3, 0.8) 随机抖动（防 WAF 封禁——2026-07-28 实测
              间隔 0.05s 跑约770只后被断流；连空 50 只会自适应休眠 30s）。
              interval_seconds=0 关闭（测试/小批量用）
            - pause: （已废弃别名）等价于 interval_seconds=(pause, pause)

    Returns:
        dict: 执行结果
    """
    scope = params.get('scope', 'all')

    logger.info("="*70)
    logger.info(f"K线数据更新任务开始 (scope={scope})")
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
        sql, query_params = build_stock_query(scope, specific_symbols)
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
def execute(**params):
    """Scheduler调用的入口函数"""
    return update_gem_klines(**params)


if __name__ == '__main__':
    # 测试执行
    result = update_gem_klines(days=5)
    print(f"\n执行结果: {result}")
