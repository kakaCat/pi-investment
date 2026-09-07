#!/usr/bin/env python3
"""
WP-6: 生产环境连接健康验证脚本

验证 BaseRepository 迁移后 idle-in-transaction 问题是否解决。
运行此脚本进行 24-48 小时监控。

Usage:
    python scripts/verify_connection_health.py
    python scripts/verify_connection_health.py --continuous --interval 300
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from infrastructure.persistence.database.engine import get_engine

def check_connection_health():
    """检查数据库连接池健康状态"""
    from psycopg2.extras import RealDictCursor
    
    engine = get_engine()
    conn = engine.connect()
    cursor = conn.connection.cursor(cursor_factory=RealDictCursor)
    
    print(f"\n{'='*60}")
    print(f"连接健康检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 1. 检查连接池状态
    print("1. 连接池状态")
    print("-" * 60)
    try:
        cursor.execute("""
            SELECT 
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active,
                count(*) FILTER (WHERE state = 'idle') as idle,
                count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                count(*) FILTER (WHERE state = 'idle in transaction (aborted)') as aborted
            FROM pg_stat_activity
            WHERE datname = current_database()
        """)
        result = cursor.fetchone()
        
        print(f"总连接数: {result['total_connections']}")
        print(f"活跃连接: {result['active']}")
        print(f"空闲连接: {result['idle']}")
        print(f"⚠️  idle in transaction: {result['idle_in_transaction']}")
        print(f"⚠️  aborted transactions: {result['aborted']}")
        
        # 检查是否存在问题
        if result['idle_in_transaction'] > 0:
            print(f"\n❌ 发现 {result['idle_in_transaction']} 个 idle in transaction 连接！")
            return False
        else:
            print("\n✅ 无 idle in transaction 连接")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # 2. 检查长时间 idle in transaction 连接
    print("\n2. 长时间 idle in transaction 连接（> 1分钟）")
    print("-" * 60)
    try:
        cursor.execute("""
            SELECT 
                pid,
                usename,
                application_name,
                state,
                state_change,
                now() - state_change as duration,
                substring(query, 1, 100) as query_preview
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND state = 'idle in transaction'
              AND state_change < now() - interval '1 minute'
            ORDER BY state_change
        """)
        
        idle_conns = cursor.fetchall()
        if idle_conns:
            print(f"❌ 发现 {len(idle_conns)} 个长时间 idle in transaction 连接：\n")
            for conn_info in idle_conns:
                print(f"  PID: {conn_info['pid']}")
                print(f"  用户: {conn_info['usename']}")
                print(f"  应用: {conn_info['application_name']}")
                print(f"  持续时间: {conn_info['duration']}")
                print(f"  查询预览: {conn_info['query_preview']}")
                print()
            return False
        else:
            print("✅ 无长时间 idle in transaction 连接")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False
    
    # 3. 检查连接泄漏迹象（连接数持续增长）
    print("\n3. 连接数趋势")
    print("-" * 60)
    try:
        cursor.execute("""
            SELECT 
                count(*) as current_connections,
                max(numbackends) as max_connections_seen
            FROM pg_stat_database
            WHERE datname = current_database()
        """)
        result = cursor.fetchone()
        
        print(f"当前连接数: {result['current_connections']}")
        print(f"历史最大连接数: {result['max_connections_seen']}")
        
        if result['current_connections'] > 15:
            print(f"\n⚠️  连接数较高（{result['current_connections']}/20）")
        else:
            print("\n✅ 连接数正常")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
    
    # 4. 检查最近的慢查询
    print("\n4. 最近慢查询（> 5秒）")
    print("-" * 60)
    try:
        cursor.execute("""
            SELECT 
                pid,
                now() - query_start as duration,
                state,
                substring(query, 1, 100) as query_preview
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND state != 'idle'
              AND query_start < now() - interval '5 seconds'
            ORDER BY query_start
        """)
        
        slow_queries = cursor.fetchall()
        if slow_queries:
            print(f"⚠️  发现 {len(slow_queries)} 个慢查询：\n")
            for query_info in slow_queries:
                print(f"  PID: {query_info['pid']}")
                print(f"  持续时间: {query_info['duration']}")
                print(f"  状态: {query_info['state']}")
                print(f"  查询预览: {query_info['query_preview']}")
                print()
        else:
            print("✅ 无慢查询")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
    
    cursor.close()
    conn.close()
    
    print(f"\n{'='*60}\n")
    return True

def continuous_monitor(interval_seconds=300):
    """持续监控连接健康（默认 5 分钟间隔）"""
    print(f"开始持续监控（间隔 {interval_seconds} 秒）...")
    print("按 Ctrl+C 停止监控\n")
    
    check_count = 0
    failed_checks = 0
    
    try:
        while True:
            check_count += 1
            print(f"\n第 {check_count} 次检查")
            
            if not check_connection_health():
                failed_checks += 1
            
            print(f"统计: {check_count} 次检查, {failed_checks} 次失败")
            print(f"下次检查: {interval_seconds} 秒后...")
            
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n\n监控已停止")
        print(f"总计: {check_count} 次检查, {failed_checks} 次失败")
        if failed_checks == 0:
            print("✅ 所有检查通过！连接池健康。")
        else:
            print(f"❌ {failed_checks} 次检查发现问题，请查看日志。")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='验证数据库连接健康')
    parser.add_argument('--continuous', action='store_true', 
                       help='持续监控模式')
    parser.add_argument('--interval', type=int, default=300,
                       help='监控间隔（秒），默认 300（5分钟）')
    
    args = parser.parse_args()
    
    if args.continuous:
        continuous_monitor(args.interval)
    else:
        # 单次检查
        success = check_connection_health()
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
