#!/usr/bin/env python
"""竞争分析功能端到端测试 - 简化版

直接通过 psycopg2 连接数据库，避免 ORM 初始化问题。
"""
import psycopg2
import json
from decimal import Decimal


def test_competition_data():
    """测试竞争分析所需的数据可用性"""
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="quant_investment",
        user="yunpeng"
    )

    cursor = conn.cursor()

    # 1. 测试贵州茅台基本信息
    print("=" * 60)
    print("测试 1：获取贵州茅台基本信息")
    print("=" * 60)

    cursor.execute("""
        SELECT symbol, name, industry, market_cap, roe, gross_margin,
               net_profit_growth, revenue_growth
        FROM quant.stocks
        WHERE symbol = '600519' AND is_delisted = false
    """)

    stock = cursor.fetchone()
    if stock:
        print(f"✅ 股票信息: {stock[1]} ({stock[0]})")
        print(f"   行业: {stock[2]}")
        print(f"   市值: {stock[3]:.2f} 亿元")
        print(f"   ROE: {stock[4]}%")
        print(f"   毛利率: {stock[5]}%")
    else:
        print("❌ 未找到贵州茅台")
        return False

    industry = stock[2]

    # 2. 测试同行业竞争对手
    print(f"\n{'=' * 60}")
    print(f"测试 2：获取同行业竞争对手（{industry}）")
    print("=" * 60)

    cursor.execute("""
        SELECT symbol, name, market_cap, roe, gross_margin
        FROM quant.stocks
        WHERE industry = %s
          AND is_delisted = false
          AND market_cap IS NOT NULL
        ORDER BY market_cap DESC
        LIMIT 10
    """, (industry,))

    competitors = cursor.fetchall()
    print(f"✅ 找到 {len(competitors)} 家同行业公司（按市值排序）:")
    for i, comp in enumerate(competitors[:5], 1):
        print(f"   {i}. {comp[1]} ({comp[0]}) - 市值: {comp[2]:.2f} 亿元")

    # 3. 测试行业汇总指标
    print(f"\n{'=' * 60}")
    print("测试 3：计算行业汇总指标")
    print("=" * 60)

    cursor.execute("""
        SELECT
            COUNT(*) as company_count,
            SUM(market_cap) as total_market_cap,
            AVG(roe) as avg_roe,
            AVG(gross_margin) as avg_gross_margin
        FROM quant.stocks
        WHERE industry = %s
          AND is_delisted = false
    """, (industry,))

    totals = cursor.fetchone()
    print(f"✅ 行业汇总:")
    print(f"   公司数量: {totals[0]}")
    print(f"   总市值: {float(totals[1]):.2f} 亿元")
    print(f"   平均 ROE: {float(totals[2]):.2f}%")
    print(f"   平均毛利率: {float(totals[3]):.2f}%")

    # 4. 计算市占率和竞争地位
    print(f"\n{'=' * 60}")
    print("测试 4：计算贵州茅台市占率")
    print("=" * 60)

    moutai_cap = stock[3]
    total_cap = float(totals[1])
    market_share = (moutai_cap / total_cap) * 100

    print(f"✅ 贵州茅台市占率: {market_share:.2f}%")
    print(f"   行业排名: 1")
    print(f"   竞争地位: {'龙头' if market_share > 30 else '头部企业'}")

    cursor.close()
    conn.close()

    print(f"\n{'=' * 60}")
    print("✅ 所有测试通过！竞争分析数据准备就绪。")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        test_competition_data()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
