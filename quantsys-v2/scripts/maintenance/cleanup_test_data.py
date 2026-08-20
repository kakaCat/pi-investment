#!/usr/bin/env python3
"""清理测试数据"""

import sys
import os

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=int(os.getenv('PGPORT', 5432)),
        database=os.getenv('PGDATABASE', 'quant_investment'),
        user=os.getenv('PGUSER', 'mac'),
        password=os.getenv('PGPASSWORD', ''),
        cursor_factory=RealDictCursor
    )

def cleanup_test_data():
    """清理测试数据"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 删除测试信号
        cursor.execute("DELETE FROM quant.signals WHERE strategy_id LIKE 'test_strategy%'")
        signal_count = cursor.rowcount
        conn.commit()
        print(f'✓ 删除了 {signal_count} 条测试信号')

        # 删除孤立的执行记录（信号已被删除）
        cursor.execute("DELETE FROM quant.signal_executions WHERE signal_id NOT IN (SELECT id FROM quant.signals)")
        execution_count = cursor.rowcount
        conn.commit()
        print(f'✓ 删除了 {execution_count} 条孤立的执行记录')

        # 删除测试持仓
        cursor.execute("DELETE FROM quant.positions WHERE symbol = '600519' AND account_id = 'default'")
        position_count = cursor.rowcount
        conn.commit()
        print(f'✓ 删除了 {position_count} 条测试持仓')

        # 删除测试股票 999999 的持仓
        cursor.execute("DELETE FROM quant.positions WHERE symbol = '999999'")
        position_count2 = cursor.rowcount
        conn.commit()
        print(f'✓ 删除了 {position_count2} 条测试股票持仓')

        print('\n清理完成！')

    except Exception as e:
        conn.rollback()
        print(f'✗ 清理失败: {str(e)}')
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    cleanup_test_data()
