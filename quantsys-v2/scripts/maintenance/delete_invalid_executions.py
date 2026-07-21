#!/usr/bin/env python3
"""
删除无效的执行记录（没有持仓却有 sell 记录）
"""
import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    # 连接数据库
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="quant_investment",
        user="mac",
        password=""
    )

    # 查询所有执行记录
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT id, signal_id, execution_date, execution_price, quantity, status
        FROM quant.signal_executions
        ORDER BY id
    """)

    records = cursor.fetchall()
    print(f"找到 {len(records)} 条执行记录")

    for record in records:
        print(f"  ID={record['id']}, signal_id={record['signal_id']}, "
              f"date={record['execution_date']}, price={record['execution_price']}, "
              f"qty={record['quantity']}, status={record['status']}")

    # 确认删除
    confirm = input("\n确认删除所有这些记录吗？(yes/no): ")
    if confirm.lower() != 'yes':
        print("取消删除")
        cursor.close()
        conn.close()
        return

    # 删除所有记录
    cursor.execute("DELETE FROM quant.signal_executions")
    conn.commit()

    print(f"\n已删除 {cursor.rowcount} 条记录")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
