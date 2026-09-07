#!/usr/bin/env python3
"""
紧急回填脚本：08-26/27 全市场K线数据
绕过 w1_backfill_klines.py 的限制（依赖持仓/池子API）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from sqlalchemy import text
from application.services.data_backfiller import DataBackfiller
from adapters.outbound.repositories.kline_repository import KlineORMRepository
from infrastructure.persistence.orm import get_session
import structlog

logger = structlog.get_logger()

def main():
    # 1. 获取所有活跃股票
    logger.info("获取活跃股票列表...")
    with get_session() as session:
        result = session.execute(text("SELECT symbol FROM quant.stocks WHERE is_delisted = false"))
        all_symbols = [row[0] for row in result]
    
    logger.info(f"活跃股票总数: {len(all_symbols)}")
    
    # 2. 检查08-26/27缺失
    backfiller = DataBackfiller(kline_repo=KlineORMRepository())
    backfill_tasks = {}
    
    logger.info("检查缺失数据...")
    for symbol in all_symbols:
        gaps = backfiller.find_kline_gaps(
            symbol=symbol, 
            start_date=date(2026, 8, 26), 
            end_date=date(2026, 8, 27)
        )
        if gaps:
            backfill_tasks[symbol] = gaps
    
    logger.info(f"需要回填的股票: {len(backfill_tasks)} 只")
    
    if not backfill_tasks:
        logger.info("数据已完整，无需回填")
        return
    
    # 3. 批量回填
    logger.info("开始批量回填...")
    result = backfiller.backfill_batch(
        backfill_tasks=backfill_tasks,
        max_workers=8,
        max_retries=3
    )
    
    logger.info("=" * 60)
    logger.info(f"回填完成:")
    logger.info(f"  成功: {result['success_count']}/{result['total_stocks']}")
    logger.info(f"  失败: {result['failure_count']}")
    logger.info(f"  回填数据: {result['total_records']} 条")
    logger.info("=" * 60)
    
    # 4. 验证
    logger.info("验证回填结果...")
    with get_session() as session:
        for trade_date in ['2026-08-26', '2026-08-27']:
            result = session.execute(text(f"SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date = '{trade_date}'"))
            count = result.scalar()
            logger.info(f"  {trade_date}: {count} 条记录")

if __name__ == '__main__':
    main()
