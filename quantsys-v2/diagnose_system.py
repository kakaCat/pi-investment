#!/usr/bin/env python3
"""
系统性诊断 - 找出交易记录API失败的根本原因
"""
import os
import sys
from pathlib import Path

print("=" * 80)
print("🔍 PI Investment 系统诊断报告")
print("=" * 80)

# 1. 环境变量检查
print("\n1️⃣ 环境变量配置检查:")
env_file = Path('.env')
if env_file.exists():
    print(f"   ✅ .env文件存在")
    with open(env_file) as f:
        for line in f:
            if 'DATABASE' in line and not line.startswith('#'):
                print(f"   📝 {line.strip()}")
else:
    print(f"   ❌ .env文件不存在")

print("\n   运行时环境变量:")
for key in ['QUANT_DATABASE_URL', 'DATABASE_URL', 'POSTGRES_DSN', 'PGDATABASE']:
    value = os.getenv(key)
    if value:
        # 隐藏密码
        if '@' in value:
            parts = value.split('@')
            value = f"{parts[0].split(':')[0]}:***@{parts[1]}"
        print(f"   ✅ {key}={value}")
    else:
        print(f"   ❌ {key} 未设置")

# 2. ORM初始化检查
print("\n2️⃣ ORM初始化检查:")
try:
    from infrastructure.persistence.orm.config import get_engine, is_initialized
    print(f"   ORM已初始化: {is_initialized()}")
    
    if not is_initialized():
        print("   尝试初始化ORM...")
        from infrastructure.persistence.orm.config import init_orm
        init_orm()
        print(f"   ✅ ORM初始化成功")
    
    engine = get_engine()
    print(f"   ✅ Engine: {engine.url}")
    
    # 检查连接
    with engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text("SELECT current_database(), current_schema()"))
        db, schema = result.fetchone()
        print(f"   ✅ 当前数据库: {db}")
        print(f"   ✅ 当前schema: {schema}")
        
except Exception as e:
    print(f"   ❌ ORM初始化失败: {e}")

# 3. 数据访问层检查
print("\n3️⃣ 数据访问层检查:")
try:
    # 3.1 Repository
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    repo = SimulationORMRepository()
    
    trades = repo.get_trades(account_name='default', limit=5)
    print(f"   ✅ Repository.get_trades(): {len(trades)}条记录")
    
    # 3.2 Service
    from application.services.simulation_service import SimulationService
    service = SimulationService()
    
    trades = service.get_trades(account_name='default', limit=5)
    print(f"   ✅ Service.get_trades(): {len(trades)}条记录")
    
except Exception as e:
    print(f"   ❌ 数据访问失败: {e}")
    import traceback
    traceback.print_exc()

# 4. Flask路由检查（Flask 已废弃删除，跳过）
print("\n4️⃣ Flask路由检查: (已废弃，Flask 已删除)")

# 5. 数据库Schema检查
print("\n5️⃣ 数据库Schema检查:")
try:
    from sqlalchemy import create_engine, text, inspect
    
    # 尝试多种连接方式
    db_urls = [
        os.getenv('QUANT_DATABASE_URL'),
        os.getenv('DATABASE_URL'),
        f"postgresql://localhost/{os.getenv('PGDATABASE', 'quant_investment')}"
    ]
    
    for db_url in db_urls:
        if not db_url:
            continue
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                # 检查表
                result = conn.execute(text("""
                    SELECT table_schema, table_name 
                    FROM information_schema.tables 
                    WHERE table_name LIKE '%simulation%'
                    ORDER BY table_schema, table_name
                """))
                
                tables = result.fetchall()
                if tables:
                    print(f"   ✅ 使用连接: {db_url.split('@')[0]}@...")
                    print(f"   模拟交易表:")
                    for schema, table in tables:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}"))
                        count = result.scalar()
                        print(f"     - {schema}.{table}: {count}条记录")
                    break
        except Exception as e:
            continue
            
except Exception as e:
    print(f"   ❌ 数据库检查失败: {e}")

# 6. start_all.py检查
print("\n6️⃣ 启动脚本检查:")
start_file = Path('start_all.py')
if start_file.exists():
    print(f"   ✅ start_all.py存在")
    with open(start_file) as f:
        content = f.read()
        if 'load_dotenv' in content:
            print(f"   ✅ 包含load_dotenv()")
        else:
            print(f"   ⚠️  可能缺少load_dotenv()")
        
        if 'QUANT_DATABASE_URL' in content or 'DATABASE_URL' in content:
            print(f"   ✅ 引用了数据库环境变量")
        else:
            print(f"   ⚠️  未明确引用数据库环境变量")
else:
    print(f"   ❌ start_all.py不存在")

print("\n" + "=" * 80)
print("📊 诊断总结:")
print("=" * 80)
