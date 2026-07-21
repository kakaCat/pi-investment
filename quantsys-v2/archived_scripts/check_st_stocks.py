"""
检查ST股票是否被选入股票池

用途：
1. 查询当前股票池中是否有ST股票
2. 验证过滤逻辑是否生效
3. 检查数据库中的股票名称数据
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.persistence.database.engine import init_engine
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def check_st_stocks():
    """检查股票池中的ST股票"""

    # 初始化连接池
    if not BaseRepository._pool_initialized:
        init_engine(pool_size=)

    conn = BaseRepository._pool.getconn()

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        print("="*80)
        print("1. 检查创业板股票池（当前过滤逻辑）")
        print("="*80)

        # 使用和 simulation_trader.py 相同的查询逻辑
        query_filtered = '''
            WITH latest_kline AS (
                SELECT DISTINCT ON (symbol)
                    symbol,
                    close,
                    volume,
                    amount,
                    turnover_rate,
                    trade_date
                FROM quant.daily_klines
                WHERE trade_date >= CURRENT_DATE - INTERVAL '10 days'
                ORDER BY symbol, trade_date DESC
            )
            SELECT s.symbol, s.name, k.amount, k.trade_date
            FROM quant.stocks s
            INNER JOIN latest_kline k ON s.symbol = k.symbol
            WHERE s.symbol LIKE '3%'
              AND s.name NOT LIKE '%ST%'                    -- 排除所有ST股票
              AND s.name NOT LIKE '*%'                      -- 排除退市整理股票
              AND s.name NOT LIKE '%退%'                    -- 排除退市相关
              AND k.amount >= 100000000                     -- 日成交额 >= 1亿
              AND k.volume > 0                              -- 有成交量
            ORDER BY k.amount DESC
            LIMIT 200
        '''

        cursor.execute(query_filtered)
        filtered_stocks = cursor.fetchall()

        print(f"过滤后的股票数量: {len(filtered_stocks)}")
        print(f"\n前20只股票:")
        for i, stock in enumerate(filtered_stocks[:20], 1):
            print(f"  {i:2d}. {stock['symbol']} {stock['name']:12s} 成交额: {stock['amount']/1e8:.2f}亿")

        print("\n" + "="*80)
        print("2. 检查过滤前的创业板股票（包含ST）")
        print("="*80)

        # 不加ST过滤条件
        query_unfiltered = '''
            WITH latest_kline AS (
                SELECT DISTINCT ON (symbol)
                    symbol,
                    close,
                    volume,
                    amount,
                    turnover_rate,
                    trade_date
                FROM quant.daily_klines
                WHERE trade_date >= CURRENT_DATE - INTERVAL '10 days'
                ORDER BY symbol, trade_date DESC
            )
            SELECT s.symbol, s.name, k.amount, k.trade_date
            FROM quant.stocks s
            INNER JOIN latest_kline k ON s.symbol = k.symbol
            WHERE s.symbol LIKE '3%'
              AND k.amount >= 100000000
              AND k.volume > 0
            ORDER BY k.amount DESC
            LIMIT 200
        '''

        cursor.execute(query_unfiltered)
        unfiltered_stocks = cursor.fetchall()

        print(f"未过滤的股票数量: {len(unfiltered_stocks)}")

        # 找出被过滤掉的股票（ST股票）
        filtered_symbols = {s['symbol'] for s in filtered_stocks}
        st_stocks = [s for s in unfiltered_stocks if s['symbol'] not in filtered_symbols]

        if st_stocks:
            print(f"\n被过滤掉的ST股票 ({len(st_stocks)}只):")
            for stock in st_stocks[:10]:
                print(f"  {stock['symbol']} {stock['name']:12s} 成交额: {stock['amount']/1e8:.2f}亿")
        else:
            print("\n未发现被过滤掉的ST股票")

        print("\n" + "="*80)
        print("3. 直接查询所有包含'ST'的创业板股票")
        print("="*80)

        query_st = '''
            SELECT symbol, name
            FROM quant.stocks
            WHERE symbol LIKE '3%'
              AND (name LIKE '%ST%' OR name LIKE '*%')
            LIMIT 50
        '''

        cursor.execute(query_st)
        st_list = cursor.fetchall()

        print(f"数据库中的ST股票数量: {len(st_list)}")
        if st_list:
            print("\n示例:")
            for stock in st_list[:20]:
                print(f"  {stock['symbol']} {stock['name']}")

        print("\n" + "="*80)
        print("4. 检查最近的模型预测结果")
        print("="*80)

        # 检查是否有交易记录表
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'quant'
                AND table_name = 'simulation_trades'
            )
        """)

        has_trades = cursor.fetchone()['exists']

        if has_trades:
            cursor.execute("""
                SELECT DISTINCT t.symbol, s.name
                FROM quant.simulation_trades t
                JOIN quant.stocks s ON t.symbol = s.symbol
                WHERE t.trade_time >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY t.trade_time DESC
                LIMIT 20
            """)

            recent_trades = cursor.fetchall()

            if recent_trades:
                print(f"最近30天的交易股票 ({len(recent_trades)}只):")
                st_traded = []
                for trade in recent_trades:
                    is_st = 'ST' in trade['name'] or trade['name'].startswith('*')
                    marker = " ⚠️ ST股票!" if is_st else ""
                    print(f"  {trade['symbol']} {trade['name']}{marker}")
                    if is_st:
                        st_traded.append(trade)

                if st_traded:
                    print(f"\n⚠️ 发现 {len(st_traded)} 只ST股票被交易!")
                    print("这些股票可能是:")
                    print("  1. 在交易后才变成ST")
                    print("  2. 股票名称数据未及时更新")
                    print("  3. 过滤逻辑未生效")
                else:
                    print("\n✓ 未发现ST股票被交易")
            else:
                print("暂无交易记录")
        else:
            print("交易记录表不存在")

        cursor.close()

    finally:
        BaseRepository._pool.putconn(conn)

    print("\n" + "="*80)
    print("检查完成")
    print("="*80)


if __name__ == '__main__':
    check_st_stocks()
