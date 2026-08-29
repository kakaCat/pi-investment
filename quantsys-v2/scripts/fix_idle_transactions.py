#!/usr/bin/env python3
"""
监控和自动终止挂起的 idle in transaction 连接

用途：
1. 检测超过阈值的挂起事务
2. 自动终止超时事务（可选）
3. 发送告警通知

运行方式：
    # 一次性检查
    python scripts/fix_idle_transactions.py --check

    # 持续监控（每 60 秒检查一次）
    python scripts/fix_idle_transactions.py --monitor --interval 60

    # 自动终止超过 5 分钟的事务
    python scripts/fix_idle_transactions.py --kill --threshold 300
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import time
import argparse
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import structlog

logger = structlog.get_logger()


def get_connection():
    """获取数据库连接"""
    import os
    dsn = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_DSN')
    if not dsn:
        # 从环境变量构造
        user = os.getenv('PGUSER', 'mac')
        password = os.getenv('PGPASSWORD', '')
        host = os.getenv('PGHOST', 'localhost')
        port = os.getenv('PGPORT', '5432')
        database = os.getenv('PGDATABASE', 'quant_investment')
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"

    return psycopg2.connect(dsn)


def find_idle_transactions(threshold_seconds=300):
    """查找超过阈值的 idle in transaction 连接

    Args:
        threshold_seconds: 阈值（秒），默认 5 分钟

    Returns:
        list[dict]: 挂起的连接列表
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    pid,
                    usename,
                    application_name,
                    client_addr,
                    backend_start,
                    state_change,
                    EXTRACT(EPOCH FROM (now() - state_change))::int as idle_seconds,
                    left(query, 200) as query
                FROM pg_stat_activity
                WHERE state = 'idle in transaction'
                  AND datname = current_database()
                  AND EXTRACT(EPOCH FROM (now() - state_change)) > %s
                ORDER BY state_change
            """, (threshold_seconds,))
            return cur.fetchall()


def terminate_connection(pid):
    """终止指定的数据库连接

    Args:
        pid: 进程 PID

    Returns:
        bool: 是否成功终止
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
            result = cur.fetchone()[0]
            conn.commit()
            return result


def check_once(threshold_seconds=300, auto_kill=False):
    """检查一次挂起的事务

    Args:
        threshold_seconds: 超时阈值（秒）
        auto_kill: 是否自动终止
    """
    idle_txns = find_idle_transactions(threshold_seconds)

    if not idle_txns:
        logger.info("no_idle_transactions", threshold=threshold_seconds)
        return

    logger.warning(
        "found_idle_transactions",
        count=len(idle_txns),
        threshold=threshold_seconds
    )

    for txn in idle_txns:
        logger.warning(
            "idle_transaction_detected",
            pid=txn['pid'],
            user=txn['usename'],
            idle_seconds=txn['idle_seconds'],
            query=txn['query'][:100]
        )

        if auto_kill:
            try:
                if terminate_connection(txn['pid']):
                    logger.info(
                        "terminated_idle_transaction",
                        pid=txn['pid'],
                        idle_seconds=txn['idle_seconds']
                    )
                else:
                    logger.error(
                        "failed_to_terminate",
                        pid=txn['pid']
                    )
            except Exception as e:
                logger.error(
                    "error_terminating_connection",
                    pid=txn['pid'],
                    error=str(e)
                )


def monitor_loop(interval=60, threshold_seconds=300, auto_kill=False):
    """持续监控挂起的事务

    Args:
        interval: 检查间隔（秒）
        threshold_seconds: 超时阈值（秒）
        auto_kill: 是否自动终止
    """
    logger.info(
        "starting_monitor",
        interval=interval,
        threshold=threshold_seconds,
        auto_kill=auto_kill
    )

    try:
        while True:
            check_once(threshold_seconds, auto_kill)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("monitor_stopped")


def main():
    parser = argparse.ArgumentParser(description='监控和终止 idle in transaction 连接')
    parser.add_argument(
        '--check',
        action='store_true',
        help='检查一次并退出'
    )
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='持续监控模式'
    )
    parser.add_argument(
        '--kill',
        action='store_true',
        help='自动终止超时事务'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=300,
        help='超时阈值（秒），默认 300 (5分钟)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='监控间隔（秒），默认 60'
    )

    args = parser.parse_args()

    if args.check:
        check_once(args.threshold, args.kill)
    elif args.monitor:
        monitor_loop(args.interval, args.threshold, args.kill)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
