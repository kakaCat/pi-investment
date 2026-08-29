"""
每日K线增量同步脚本
用途：同步指定日期的所有活跃股票K线数据
调用：python sync_daily_klines_incremental.py --date YYYY-MM-DD
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import structlog
from datetime import datetime, timedelta
from typing import List, Set
from application.services.data_backfiller import DataBackfiller
from adapters.outbound.repositories.kline_repository import KlineORMRepository
from infrastructure.persistence.orm import get_session

logger = structlog.get_logger(__name__)


def get_active_stocks() -> Set[str]:
    """获取所有活跃股票代码（未退市）"""
    try:
        session = get_session()
        from infrastructure.persistence.orm.models import Stock
        
        stocks = session.query(Stock.symbol).filter(
            Stock.is_delisted == False
        ).all()
        
        symbols = {s[0] for s in stocks}
        logger.info(f"获取活跃股票: {len(symbols)} 只")
        return symbols
        
    except Exception as e:
        logger.error(f"获取活跃股票失败: {e}")
        raise


def sync_daily_klines(sync_date: str):
    """同步指定日期的K线数据"""
    logger.info(f"=" * 60)
    logger.info(f"每日K线增量同步")
    logger.info(f"同步日期: {sync_date}")
    logger.info(f"=" * 60)
    
    # 获取活跃股票
    symbols = get_active_stocks()
    
    if not symbols:
        logger.error("未获取到任何股票，退出")
        sys.exit(1)
    
    # 构建回填任务（单日）
    kline_repo = KlineORMRepository()
    backfiller = DataBackfiller(kline_repo=kline_repo)
    
    backfill_tasks = {}
    for symbol in symbols:
        backfill_tasks[symbol] = [{
            'start': sync_date,
            'end': sync_date,
            'days': 1
        }]
    
    logger.info(f"开始同步 {len(symbols)} 只股票的 {sync_date} K线数据...")
    
    # 执行批量回填
    start_time = datetime.now()
    result = backfiller.backfill_batch(
        backfill_tasks=backfill_tasks,
        max_workers=10,  # 增量同步可以提高并发
        max_retries=3
    )
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # 输出结果
    logger.info(f"=" * 60)
    logger.info(f"同步完成:")
    logger.info(f"  成功: {result['success_count']}/{result['total_stocks']}")
    logger.info(f"  失败: {result['failed_count']}")
    logger.info(f"  回填数据: {result['total_days_filled']} 条")
    logger.info(f"  耗时: {elapsed:.1f}s")
    
    if result['failed_symbols']:
        logger.warning(f"  失败股票（前10）: {result['failed_symbols'][:10]}")
    
    # 验证结果
    success_rate = result['success_count'] / result['total_stocks'] if result['total_stocks'] > 0 else 0
    expected_rows = result['total_stocks']  # 每只股票1条
    actual_rows = result['total_days_filled']
    
    logger.info(f"验收指标:")
    logger.info(f"  成功率: {success_rate*100:.1f}% (期望 ≥80%)")
    logger.info(f"  数据量: {actual_rows}/{expected_rows} 条 (期望 ≥{int(expected_rows*0.8)})")
    
    if success_rate < 0.8:
        logger.error(f"❌ 成功率不达标: {success_rate*100:.1f}% < 80%")
        sys.exit(1)
    
    if actual_rows < expected_rows * 0.8:
        logger.error(f"❌ 数据量不达标: {actual_rows} < {int(expected_rows*0.8)}")
        sys.exit(1)
    
    logger.info(f"✅ 同步成功，验收通过")
    logger.info(f"=" * 60)


def main():
    parser = argparse.ArgumentParser(description='每日K线增量同步')
    parser.add_argument(
        '--date',
        type=str,
        help='同步日期 YYYY-MM-DD（默认昨日）',
        default=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    )
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        logger.error(f"无效日期格式: {args.date}，应为 YYYY-MM-DD")
        sys.exit(1)
    
    # 执行同步
    try:
        sync_daily_klines(args.date)
    except Exception as e:
        logger.exception(f"同步失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
