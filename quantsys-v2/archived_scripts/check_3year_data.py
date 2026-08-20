#!/usr/bin/env python3
"""
检查哪些股票缺少3年历史数据

输出需要补充数据的股票列表，按优先级排序
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent

# 加载环境变量
from dotenv import load_dotenv
env_path = project_root.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import StockORMRepository


def check_3year_data():
    """检查3年数据完整性"""

    kline_repo = KlineORMRepository()
    stock_repo = StockORMRepository()

    # 计算时间范围
    end_date = datetime.now()
    start_date_3y = end_date - timedelta(days=365 * 3)

    # 预期的3年交易日数量（约 240天/年 × 3年 = 720天）
    expected_days_3y = 720
    min_acceptable_3y = int(expected_days_3y * 0.8)  # 至少要有80%的数据（576天）

    print("=" * 80)
    print("3年历史数据完整性检查")
    print("=" * 80)
    print(f"检查时间范围: {start_date_3y.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"预期交易日数: {expected_days_3y} 天")
    print(f"最低要求: {min_acceptable_3y} 天 (80%)")
    print()

    # 获取所有股票
    cursor = kline_repo.db.cursor()
    cursor.execute("""
        SELECT DISTINCT symbol
        FROM quant.daily_klines
        ORDER BY symbol
    """)
    all_symbols = [row['symbol'] for row in cursor.fetchall()]
    cursor.close()

    print(f"数据库中共有 {len(all_symbols)} 只股票")
    print()
    print("正在检查数据完整性...")
    print()

    # 分类统计
    complete = []           # 数据完整（≥80%）
    insufficient = []       # 数据不足（< 80%）
    no_recent_data = []     # 最近数据缺失（最新数据超过30天）

    for i, symbol in enumerate(all_symbols, 1):
        if i % 500 == 0:
            print(f"进度: {i}/{len(all_symbols)}")

        # 获取日期范围
        date_range = kline_repo.get_available_date_range(symbol)
        if not date_range:
            insufficient.append({
                'symbol': symbol,
                'count': 0,
                'expected': expected_days_3y,
                'coverage': 0.0,
                'min_date': None,
                'max_date': None,
                'issue': '无数据'
            })
            continue

        min_date, max_date = date_range
        max_date_obj = datetime.strptime(max_date, '%Y-%m-%d')

        # 检查最近数据是否过时
        days_since_update = (end_date - max_date_obj).days

        # 统计3年内的数据量
        count_3y = kline_repo.get_kline_count(
            symbol,
            start_date_3y.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        coverage = count_3y / expected_days_3y if expected_days_3y > 0 else 0

        stock_info = {
            'symbol': symbol,
            'count': count_3y,
            'expected': expected_days_3y,
            'coverage': coverage,
            'min_date': min_date,
            'max_date': max_date,
            'days_since_update': days_since_update
        }

        # 分类
        if days_since_update > 30:
            stock_info['issue'] = f'最近数据缺失（{days_since_update}天未更新）'
            no_recent_data.append(stock_info)
        elif count_3y < min_acceptable_3y:
            missing = expected_days_3y - count_3y
            stock_info['issue'] = f'数据不足（缺失约{missing}天）'
            insufficient.append(stock_info)
        else:
            complete.append(stock_info)

    # 输出结果
    print()
    print("=" * 80)
    print("检查结果")
    print("=" * 80)
    print()

    print(f"✅ 数据完整（≥80%）: {len(complete)} 只股票")
    print(f"⚠️  数据不足（<80%）: {len(insufficient)} 只股票")
    print(f"🚫 最近数据缺失: {len(no_recent_data)} 只股票")
    print()

    # 输出需要补充数据的股票
    total_need_backfill = len(insufficient) + len(no_recent_data)

    if total_need_backfill == 0:
        print("🎉 所有股票的3年数据都完整！")
        return

    print("=" * 80)
    print(f"需要补充数据的股票 (共 {total_need_backfill} 只)")
    print("=" * 80)
    print()

    # 按优先级排序：活跃股票优先（最近有更新的）
    need_backfill = insufficient + no_recent_data
    need_backfill.sort(key=lambda x: (x['days_since_update'], -x['count']))

    # 输出详细列表（前100个）
    print("【优先级高】最近活跃但数据不足的股票 (前100):")
    print("-" * 80)
    print(f"{'股票代码':<10} {'数据量':<10} {'覆盖率':<10} {'最新日期':<12} {'问题'}")
    print("-" * 80)

    active_stocks = [s for s in need_backfill if s['days_since_update'] <= 30]
    for stock in active_stocks[:100]:
        coverage_pct = f"{stock['coverage']*100:.1f}%"
        print(f"{stock['symbol']:<10} {stock['count']:<10} {coverage_pct:<10} "
              f"{stock['max_date']:<12} {stock['issue']}")

    print()
    print("【优先级中】较久未更新但曾活跃的股票:")
    print("-" * 80)

    inactive_stocks = [s for s in need_backfill if 30 < s['days_since_update'] <= 365]
    print(f"共 {len(inactive_stocks)} 只股票（30天-1年未更新）")
    if inactive_stocks:
        print(f"示例: {', '.join([s['symbol'] for s in inactive_stocks[:10]])}")

    print()
    print("【优先级低】长期停牌/退市股票:")
    print("-" * 80)

    retired_stocks = [s for s in need_backfill if s['days_since_update'] > 365]
    print(f"共 {len(retired_stocks)} 只股票（超过1年未更新）")
    if retired_stocks:
        print(f"示例: {', '.join([s['symbol'] for s in retired_stocks[:10]])}")

    print()
    print("=" * 80)
    print("数据导出")
    print("=" * 80)
    print()

    # 导出需要补充的股票列表
    output_file = project_root / 'scripts' / 'stocks_need_3year_backfill.txt'
    with open(output_file, 'w') as f:
        f.write("# 需要补充3年历史数据的股票列表\n")
        f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 总数: {total_need_backfill}\n")
        f.write("#\n")
        f.write("# 格式: 股票代码 | 当前数据量 | 覆盖率 | 最新日期 | 天数差 | 问题\n")
        f.write("#\n\n")

        f.write("# ===== 优先级高（活跃股票）=====\n")
        for stock in active_stocks:
            f.write(f"{stock['symbol']}|{stock['count']}|{stock['coverage']:.2%}|"
                   f"{stock['max_date']}|{stock['days_since_update']}|{stock['issue']}\n")

        f.write("\n# ===== 优先级中（较久未更新）=====\n")
        for stock in inactive_stocks:
            f.write(f"{stock['symbol']}|{stock['count']}|{stock['coverage']:.2%}|"
                   f"{stock['max_date']}|{stock['days_since_update']}|{stock['issue']}\n")

        f.write("\n# ===== 优先级低（可能退市）=====\n")
        for stock in retired_stocks:
            f.write(f"{stock['symbol']}|{stock['count']}|{stock['coverage']:.2%}|"
                   f"{stock['max_date']}|{stock['days_since_update']}|{stock['issue']}\n")

    print(f"✅ 股票清单已导出到: {output_file}")
    print()

    # 输出补充建议
    print("=" * 80)
    print("补充建议")
    print("=" * 80)
    print()
    print("建议分阶段补充数据：")
    print()
    print(f"1. 【第一批】活跃股票 ({len(active_stocks)} 只)")
    print(f"   这些股票最近仍在交易，优先补充3年历史数据")
    print(f"   命令: python scripts/backfill_active_stocks.py --from-file stocks_need_3year_backfill.txt")
    print()
    print(f"2. 【第二批】较久未更新 ({len(inactive_stocks)} 只)")
    print(f"   这些股票可能停牌或不活跃，根据需要补充")
    print()
    print(f"3. 【跳过】长期停牌/退市 ({len(retired_stocks)} 只)")
    print(f"   建议标记为非活跃，不再补充数据")
    print()


if __name__ == '__main__':
    try:
        check_3year_data()
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
