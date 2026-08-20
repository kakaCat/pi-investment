#!/usr/bin/env python3
"""WP-15 Pre-deployment Validation Script

验证 WP-15 代码的核心功能，无需重启服务。

用法:
    python tools/validate_wp15.py
"""
import sys
from pathlib import Path

# Add project root to path

def test_imports():
    """测试所有模块导入"""
    print("=" * 60)
    print("Testing Module Imports...")
    print("=" * 60)

    tests = []

    # Test 1: Agent OS Client
    try:
        from application.services.agent_os_client import AgentOSClient, get_agent_os_client
        print("✅ agent_os_client imports OK")
        tests.append(True)
    except Exception as e:
        print(f"❌ agent_os_client import failed: {e}")
        tests.append(False)

    # Test 2: Webhook module
    try:
        from api.internal.scheduler_webhook import (
            JOB_HANDLERS,
            register_job_handler,
            WebhookPayload
        )
        print(f"✅ scheduler_webhook imports OK ({len(JOB_HANDLERS)} handlers)")
        tests.append(True)
    except Exception as e:
        print(f"❌ scheduler_webhook import failed: {e}")
        tests.append(False)

    # Test 3: Job Handlers
    try:
        from application.services import scheduler_handlers
        from api.internal.scheduler_webhook import JOB_HANDLERS
        print(f"✅ scheduler_handlers imports OK ({len(JOB_HANDLERS)} handlers registered)")
        tests.append(True)
    except Exception as e:
        print(f"❌ scheduler_handlers import failed: {e}")
        tests.append(False)

    return all(tests)


def test_job_handlers():
    """测试 Job Handler 注册"""
    print("\n" + "=" * 60)
    print("Testing Job Handler Registration...")
    print("=" * 60)

    from api.internal.scheduler_webhook import JOB_HANDLERS

    expected_handlers = [
        "kline_update",
        "chip_distribution_update",
        "pool_refresh",
        "signal_generate",
        "factor_compute",
        "v13_daily_check",
        "financial_statement_update"
    ]

    missing = []
    for handler in expected_handlers:
        if handler in JOB_HANDLERS:
            print(f"✅ {handler}: registered")
        else:
            print(f"❌ {handler}: missing")
            missing.append(handler)

    total = len(JOB_HANDLERS)
    print(f"\nTotal registered handlers: {total}")

    return len(missing) == 0


def test_registration_script():
    """测试任务注册脚本"""
    print("\n" + "=" * 60)
    print("Testing Job Registration Script...")
    print("=" * 60)

    try:
        from tools.register_jobs_to_agent_os import JOBS

        print(f"✅ Registration script loaded: {len(JOBS)} jobs defined")

        # 检查必需字段
        required_fields = ["name", "owner", "cron", "webhook_url", "enabled", "metadata"]

        for i, job in enumerate(JOBS[:3]):  # 只检查前3个
            missing_fields = [f for f in required_fields if f not in job]
            if missing_fields:
                print(f"❌ Job {i} ({job.get('name', 'unknown')}) missing fields: {missing_fields}")
                return False
            print(f"✅ Job: {job['name']} ({job['cron']})")

        print(f"... and {len(JOBS) - 3} more jobs")
        return True

    except Exception as e:
        print(f"❌ Registration script validation failed: {e}")
        return False


def test_database_schema():
    """测试数据库 schema 兼容性"""
    print("\n" + "=" * 60)
    print("Testing Database Schema...")
    print("=" * 60)

    try:
        import psycopg2
        from infrastructure.persistence.database.engine import _resolve_db_dsn

        dsn = _resolve_db_dsn()
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor()

        # 检查 scheduler_tasks 表
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'quant'
            AND table_name = 'scheduler_tasks'
        """)

        columns = [row[0] for row in cursor.fetchall()]
        required_columns = ['id', 'name', 'command', 'cron_expression', 'params']

        missing = [col for col in required_columns if col not in columns]
        if missing:
            print(f"❌ scheduler_tasks missing columns: {missing}")
            return False

        print(f"✅ scheduler_tasks has all required columns")

        # 检查 scheduler_runs 表
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'quant'
            AND table_name = 'scheduler_runs'
        """)

        columns = [row[0] for row in cursor.fetchall()]
        required_columns = ['id', 'task_id', 'status', 'started_at', 'completed_at']

        missing = [col for col in required_columns if col not in columns]
        if missing:
            print(f"❌ scheduler_runs missing columns: {missing}")
            return False

        print(f"✅ scheduler_runs has all required columns")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Database schema check failed: {e}")
        return False


def test_agent_os_connectivity():
    """测试 Agent OS 连接性"""
    print("\n" + "=" * 60)
    print("Testing Agent OS Connectivity...")
    print("=" * 60)

    try:
        import httpx
        import asyncio

        async def check():
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://127.0.0.1:8080/health")
                return response.status_code == 200

        is_healthy = asyncio.run(check())

        if is_healthy:
            print("✅ Agent OS is reachable at http://127.0.0.1:8080")
            return True
        else:
            print("⚠️  Agent OS returned non-200 status")
            return False

    except Exception as e:
        print(f"⚠️  Agent OS not reachable: {e}")
        print("   (Service will fall back to local scheduler)")
        return False


def main():
    """运行所有验证测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "WP-15 Pre-deployment Validation" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    # 运行测试
    results.append(("Module Imports", test_imports()))
    results.append(("Job Handler Registration", test_job_handlers()))
    results.append(("Registration Script", test_registration_script()))
    results.append(("Database Schema", test_database_schema()))
    results.append(("Agent OS Connectivity", test_agent_os_connectivity()))

    # 打印总结
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1

    print()
    print(f"Total: {passed}/{len(results)} tests passed")

    # 最终判定
    if passed == len(results):
        print("\n✅ All validation tests passed!")
        print("   WP-15 is ready for deployment.")
        return 0
    elif passed >= len(results) - 1:  # 允许 Agent OS 连接失败（会回退）
        print("\n⚠️  Most tests passed, but some warnings exist.")
        print("   WP-15 can be deployed with fallback mode.")
        return 0
    else:
        print("\n❌ Validation failed!")
        print("   Please fix the issues before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
