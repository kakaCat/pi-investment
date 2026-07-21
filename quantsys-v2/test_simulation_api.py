#!/usr/bin/env python3
"""
测试模拟交易API - 诊断为什么API返回空数据
"""
import os
os.environ['DATABASE_URL'] = 'postgresql://localhost/quant_investment'

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from application.services.simulation_service import SimulationService

print("=" * 80)
print("🔍 模拟交易API诊断")
print("=" * 80)

# 测试1: 直接使用Repository
print("\n1️⃣ 测试Repository.get_trades():")
try:
    repo = SimulationORMRepository()
    trades = repo.get_trades(account_name='default', limit=10)
    print(f"   返回记录数: {len(trades)}")
    if trades:
        for i, trade in enumerate(trades[:5], 1):
            print(f"   {i}. {trade.trade_date} {trade.action} {trade.symbol} {trade.shares}股")
    else:
        print("   ⚠️  返回空列表")

        # 尝试直接SQL查询
        from sqlalchemy import text
        engine = repo.session.get_bind()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM quant.simulation_trades WHERE account_name = 'default'"))
            count = result.scalar()
            print(f"   💡 直接SQL查询结果: {count}条记录")
except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 测试2: 使用Service
print("\n2️⃣ 测试SimulationService.get_trades():")
try:
    service = SimulationService()
    trades = service.get_trades(account_name='default', limit=10)
    print(f"   返回记录数: {len(trades)}")
    if trades:
        for i, trade in enumerate(trades[:5], 1):
            print(f"   {i}. {trade}")
    else:
        print("   ⚠️  返回空列表")
except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 测试3: 检查ORM配置
print("\n3️⃣ 检查ORM配置:")
try:
    from infrastructure.persistence.orm.config import get_engine
    from sqlalchemy import inspect

    engine = get_engine()
    inspector = inspect(engine)

    # 检查search_path
    with engine.connect() as conn:
        result = conn.execute(text("SHOW search_path"))
        search_path = result.scalar()
        print(f"   search_path: {search_path}")

        # 检查表是否可见
        result = conn.execute(text("SELECT COUNT(*) FROM simulation_trades WHERE account_name = 'default'"))
        count = result.scalar()
        print(f"   simulation_trades (无schema): {count}条")

        result = conn.execute(text("SELECT COUNT(*) FROM quant.simulation_trades WHERE account_name = 'default'"))
        count = result.scalar()
        print(f"   quant.simulation_trades: {count}条")

except Exception as e:
    print(f"   ❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
