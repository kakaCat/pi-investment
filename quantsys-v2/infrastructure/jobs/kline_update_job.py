"""
K线数据更新Job - 使用多数据源自动更新

每日自动更新创业板K线数据，支持多数据源fallback
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from adapters.outbound.datasources.manager import DataProviderManager
from infrastructure.persistence.database.engine import get_engine

logger = logging.getLogger(__name__)


def update_gem_klines(**params):
    """
    更新创业板K线数据

    Args:
        **params: 任务参数
            - days: 更新最近N天的数据（默认5天）
            - symbols: 指定股票代码列表（可选）

    Returns:
        dict: 执行结果
    """
    logger.info("="*70)
    logger.info("创业板K线数据更新任务开始")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)

    days = params.get('days', 5)
    specific_symbols = params.get('symbols', None)

    engine = None
    conn = None

    try:
        # 初始化
        engine = get_engine()
        conn = engine.raw_connection()
        cursor = conn.cursor()

        # 获取股票列表
        if specific_symbols:
            placeholders = ','.join(['%s'] * len(specific_symbols))
            cursor.execute(f"""
                SELECT symbol, name
                FROM quant.stocks
                WHERE symbol IN ({placeholders})
                ORDER BY symbol
            """, specific_symbols)
        else:
            cursor.execute("""
                SELECT symbol, name
                FROM quant.stocks
                WHERE (symbol LIKE '300%' OR symbol LIKE '301%')
                  AND name NOT LIKE '%退%'
                  AND name NOT LIKE '%ST%'
                ORDER BY symbol
            """)

        stocks = cursor.fetchall()
        total = len(stocks)
        logger.info(f"需要更新: {total}只股票")

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"日期范围: {start_date} -> {end_date}")

        # 初始化数据源管理器
        manager = DataProviderManager()

        success = 0
        failed = 0
        skipped = 0

        for i, (symbol, name) in enumerate(stocks, 1):
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
                    logger.debug(f"[{i}/{total}] {symbol} - 无数据")
                    continue

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
                        0.0,  # turnover_rate: KlineData 契约无此字段
                    ))
                    inserted += 1

                conn.commit()
                success += 1

                if i % 100 == 0:
                    logger.info(f"进度: [{i}/{total}] 成功{success} 失败{failed} 跳过{skipped}")

            except Exception as e:
                failed += 1
                logger.warning(f"[{i}/{total}] {symbol} - 失败: {str(e)[:50]}")
                conn.rollback()

        cursor.close()

        result = {
            'action': 'kline_update',
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'date_range': f"{start_date} -> {end_date}",
            'message': f'K线更新完成: 成功{success}只, 失败{failed}只, 跳过{skipped}只'
        }

        logger.info("="*70)
        logger.info(f"✅ K线更新完成")
        logger.info(f"  成功: {success}只")
        logger.info(f"  失败: {failed}只")
        logger.info(f"  跳过: {skipped}只")
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
