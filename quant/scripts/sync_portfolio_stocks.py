#!/usr/bin/env python3
"""
同步持仓股票数据到量化项目

从主项目的 portfolio.json 读取持仓股票，
然后获取这些股票的历史数据并存入量化项目数据库
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def load_portfolio():
    """从主项目加载持仓数据"""
    portfolio_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        '.pi-invest', 'portfolio.json'
    )

    logger.info(f"读取持仓文件: {portfolio_path}")

    if not os.path.exists(portfolio_path):
        logger.error(f"持仓文件不存在: {portfolio_path}")
        return []

    with open(portfolio_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    holdings = data.get('holdings', [])
    logger.info(f"找到 {len(holdings)} 只持仓股票")

    return holdings


def filter_a_share_stocks(holdings):
    """筛选A股股票（排除港股和ETF）"""
    a_stocks = []

    for holding in holdings:
        symbol = holding.get('symbol', '')
        market = holding.get('market', 'A')
        name = holding.get('name', '')

        # 跳过港股
        if market == 'HK':
            logger.info(f"跳过港股: {symbol} {name}")
            continue

        # 跳过ETF（代码以5开头）
        if symbol.startswith('5'):
            logger.info(f"跳过ETF: {symbol} {name}")
            continue

        a_stocks.append({
            'symbol': symbol,
            'name': name,
            'quantity': holding.get('quantity', 0),
            'avg_cost': holding.get('avg_cost', 0),
            'sector': holding.get('sector', ''),
            'buy_reason': holding.get('buy_reason', '')
        })

    logger.info(f"筛选出 {len(a_stocks)} 只A股")
    return a_stocks


def sync_stock_data(db, fetcher, stocks, days=500):
    """同步股票数据"""
    logger.info("=" * 60)
    logger.info(f"开始同步 {len(stocks)} 只股票的数据（最近{days}天）")
    logger.info("=" * 60)

    success_count = 0
    fail_count = 0

    for i, stock in enumerate(stocks, 1):
        symbol = stock['symbol']
        name = stock['name']

        logger.info(f"\n[{i}/{len(stocks)}] 处理: {symbol} {name}")

        try:
            # 检查现有数据
            cursor = db.conn.cursor()
            existing = cursor.execute(
                "SELECT COUNT(*) as count, MIN(date) as first_date, MAX(date) as last_date "
                "FROM daily_klines WHERE symbol = ?",
                (symbol,)
            ).fetchone()

            if existing and existing['count'] > 0:
                logger.info(f"  现有数据: {existing['count']}条 "
                          f"({existing['first_date']} 至 {existing['last_date']})")
            else:
                logger.info(f"  现有数据: 无")

            # 获取数据
            logger.info(f"  正在获取最近{days}天的数据...")
            fetcher.run(symbols=[symbol], days=days, market='A')

            # 检查更新后的数据
            updated = cursor.execute(
                "SELECT COUNT(*) as count, MIN(date) as first_date, MAX(date) as last_date "
                "FROM daily_klines WHERE symbol = ?",
                (symbol,)
            ).fetchone()

            if updated and updated['count'] > 0:
                logger.info(f"  ✅ 更新后: {updated['count']}条 "
                          f"({updated['first_date']} 至 {updated['last_date']})")
                success_count += 1
            else:
                logger.warning(f"  ⚠️  未获取到数据")
                fail_count += 1

        except Exception as e:
            logger.error(f"  ❌ 失败: {e}")
            fail_count += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"同步完成: 成功 {success_count} 只，失败 {fail_count} 只")
    logger.info("=" * 60)

    return success_count, fail_count


def print_summary(db, stocks):
    """打印数据汇总"""
    logger.info("\n" + "=" * 60)
    logger.info("持仓股票数据汇总")
    logger.info("=" * 60)

    print("\n{:<10} {:<10} {:<8} {:<12} {:<12} {:<12}".format(
        "代码", "名称", "持仓", "成本", "数据天数", "最新日期"
    ))
    print("-" * 80)

    cursor = db.conn.cursor()

    for stock in stocks:
        symbol = stock['symbol']
        name = stock['name']
        quantity = stock['quantity']
        avg_cost = stock['avg_cost']

        # 查询数据
        result = cursor.execute(
            "SELECT COUNT(*) as days, MAX(date) as last_date "
            "FROM daily_klines WHERE symbol = ?",
            (symbol,)
        ).fetchone()

        days = result['days'] if result else 0
        last_date = result['last_date'] if result else 'N/A'

        print("{:<10} {:<10} {:<8} {:<12.2f} {:<12} {:<12}".format(
            symbol, name, quantity, avg_cost, days, last_date
        ))

    # 总体统计
    total_stocks = len(stocks)
    total_records = cursor.execute(
        "SELECT COUNT(*) as count FROM daily_klines WHERE symbol IN ({})".format(
            ','.join(['?'] * len(stocks))
        ),
        tuple(s['symbol'] for s in stocks)
    ).fetchone()['count']

    print("-" * 80)
    print(f"总计: {total_stocks} 只股票，{total_records} 条K线记录")
    print("=" * 60)


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("持仓股票数据同步工具")
    logger.info("=" * 60)

    # 1. 加载持仓
    holdings = load_portfolio()
    if not holdings:
        logger.error("未找到持仓数据")
        return

    # 2. 筛选A股
    a_stocks = filter_a_share_stocks(holdings)
    if not a_stocks:
        logger.error("未找到A股持仓")
        return

    # 3. 打印持仓列表
    logger.info("\n持仓A股列表:")
    for i, stock in enumerate(a_stocks, 1):
        logger.info(f"  {i}. {stock['symbol']} {stock['name']} "
                   f"({stock['quantity']}股 @{stock['avg_cost']})")

    # 4. 初始化数据库
    db_path = os.path.join(
        os.path.expanduser('~'),
        '.pi-invest', 'stock-db', 'stocks.db'
    )
    logger.info(f"\n数据库路径: {db_path}")

    db = Database(db_path)
    fetcher = KlineFetcher(db)

    # 5. 同步数据
    success, fail = sync_stock_data(
        db,
        fetcher,
        a_stocks,
        days=500  # 获取最近500天数据（约2年）
    )

    # 6. 打印汇总
    print_summary(db, a_stocks)

    # 7. 完成
    logger.info("\n✅ 同步完成！")
    logger.info(f"成功: {success} 只")
    logger.info(f"失败: {fail} 只")

    if success > 0:
        logger.info("\n下一步:")
        logger.info("  1. 计算因子: python3 scripts/calculate_factors.py")
        logger.info("  2. 生成信号: python3 scripts/generate_signals.py")
        logger.info("  3. 风险检查: python3 scripts/risk_check.py")


if __name__ == '__main__':
    main()
