#!/usr/bin/env python
"""
数据补救脚本 - 补充缺失的历史数据

Usage:
    python scripts/backfill_data.py --days 10
    python scripts/backfill_data.py --start-date 2026-05-15 --end-date 2026-05-25
"""
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from application.services.data_service import DataService


def update_stock_kline(ds: DataService, symbol: str, start_date: str, end_date: str) -> dict:
    """更新单个股票的 K 线数据"""
    try:
        # 获取历史 K 线数据
        klines = ds.kline.get_daily_klines(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )

        if klines:
            logger.info(f"✓ {symbol}: 获取到 {len(klines)} 条 K 线数据")
            return {'symbol': symbol, 'count': len(klines), 'success': True}
        else:
            logger.warning(f"⚠ {symbol}: 未获取到数据")
            return {'symbol': symbol, 'count': 0, 'success': False}

    except Exception as e:
        logger.error(f"✗ {symbol}: 更新失败 - {e}")
        return {'symbol': symbol, 'error': str(e), 'success': False}


def backfill_market_data(market: str = 'A', days: int = None,
                         start_date: str = None, end_date: str = None,
                         max_workers: int = 8, limit: int = None):
    """
    补充市场数据

    Args:
        market: 市场代码 ('A', 'HK', 'US')
        days: 回溯天数（如果未指定 start_date）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        max_workers: 并行工作线程数
        limit: 限制更新的股票数量（用于测试）
    """
    ds = DataService()

    # 计算日期范围
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    if start_date is None:
        if days is None:
            days = 10
        start_dt = datetime.now() - timedelta(days=days)
        start_date = start_dt.strftime('%Y-%m-%d')

    logger.info(f"=" * 60)
    logger.info(f"开始数据补救: {market} 市场")
    logger.info(f"日期范围: {start_date} 至 {end_date}")
    logger.info(f"并行线程: {max_workers}")
    logger.info(f"=" * 60)

    # 获取股票列表
    stocks = ds.stock.get_all(market=market, limit=limit or 1000)
    total_stocks = len(stocks)
    logger.info(f"待更新股票数: {total_stocks}")

    if total_stocks == 0:
        logger.warning("没有找到股票数据，请先运行 scripts/init_stocks.py")
        return

    # 并行更新
    results = []
    success_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {
            executor.submit(update_stock_kline, ds, stock['symbol'], start_date, end_date): stock
            for stock in stocks
        }

        # 处理完成的任务
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)

            if result['success']:
                success_count += 1
            else:
                error_count += 1

            # 每 50 个打印进度
            if i % 50 == 0:
                logger.info(f"进度: {i}/{total_stocks} ({i*100//total_stocks}%) - "
                          f"成功: {success_count}, 失败: {error_count}")

    # 汇总结果
    logger.info(f"=" * 60)
    logger.info(f"数据补救完成!")
    logger.info(f"总计: {total_stocks} 只股票")
    logger.info(f"成功: {success_count} ({success_count*100//total_stocks}%)")
    logger.info(f"失败: {error_count} ({error_count*100//total_stocks}%)")
    logger.info(f"=" * 60)

    # 显示失败的股票
    if error_count > 0:
        logger.warning(f"\n失败的股票 (前 10 个):")
        failed = [r for r in results if not r['success']][:10]
        for r in failed:
            logger.warning(f"  - {r['symbol']}: {r.get('error', '未获取到数据')}")


def main():
    parser = argparse.ArgumentParser(description='数据补救脚本')
    parser.add_argument('--market', default='A', choices=['A', 'HK', 'US'],
                       help='市场代码 (默认: A)')
    parser.add_argument('--days', type=int,
                       help='回溯天数 (默认: 10)')
    parser.add_argument('--start-date',
                       help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end-date',
                       help='结束日期 YYYY-MM-DD (默认: 今天)')
    parser.add_argument('--workers', type=int, default=8,
                       help='并行工作线程数 (默认: 8)')
    parser.add_argument('--limit', type=int,
                       help='限制更新的股票数量 (用于测试)')

    args = parser.parse_args()

    try:
        backfill_market_data(
            market=args.market,
            days=args.days,
            start_date=args.start_date,
            end_date=args.end_date,
            max_workers=args.workers,
            limit=args.limit
        )
    except KeyboardInterrupt:
        logger.info("\n用户中断，退出...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
