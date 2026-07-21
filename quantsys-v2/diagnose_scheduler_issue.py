#!/usr/bin/env python3
"""
彻底诊断 Scheduler API 问题
找出为什么 HTTP 返回 0，但直接调用返回 6
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from dotenv import load_dotenv
load_dotenv(Path('.env'))

print("=" * 70)
print("Scheduler API 问题诊断")
print("=" * 70)

# 1. 测试直接调用
print("\n1. 直接调用 get_tasks 函数")
print("-" * 70)
from adapters.inbound.fastapi_app.routes.scheduler_async import get_tasks
import asyncio

async def test_direct():
    result = await get_tasks(page=1, pageSize=12)
    return result

result = asyncio.run(test_direct())
print(f"结果: Total={result['data']['total']}, Items={len(result['data']['items'])}")

# 2. 检查实际的 get_session
print("\n2. 检查 get_session() 返回的连接")
print("-" * 70)
from infrastructure.persistence.orm.config import get_session
from sqlalchemy import text

session = get_session()
print(f"Session: {session}")
print(f"Bind: {session.bind}")
print(f"URL: {session.bind.url}")

count = session.execute(text("SELECT COUNT(*) FROM scheduler_tasks WHERE deleted_at IS NULL")).scalar()
print(f"数据库查询: {count} 条记录")

# 3. 检查是否有多个数据库配置
print("\n3. 检查环境变量")
print("-" * 70)
import os
env_vars = ['QUANT_DATABASE_URL', 'DATABASE_URL', 'POSTGRES_DSN', 
            'PGHOST', 'PGDATABASE', 'PGUSER', 'PGPORT']
for var in env_vars:
    value = os.getenv(var)
    if value:
        # 隐藏密码
        if 'postgresql://' in value:
            parts = value.split('@')
            if len(parts) > 1:
                value = parts[0].split(':')[0] + ':***@' + parts[1]
        print(f"{var}: {value}")
    else:
        print(f"{var}: (未设置)")

# 4. 读取实际运行的代码
print("\n4. 检查实际加载的代码")
print("-" * 70)
import inspect
source = inspect.getsource(get_tasks)
if 'get_session()' in source:
    print("✅ 代码包含 get_session()")
else:
    print("❌ 代码不包含 get_session()")

if 'SchedulerConfigORMRepository' in source:
    print("⚠️  代码仍在使用 SchedulerConfigORMRepository (旧代码)")
else:
    print("✅ 代码已更新")

# 5. 检查文件修改时间
print("\n5. 检查文件时间戳")
print("-" * 70)
import os.path
file_path = Path('adapters/inbound/fastapi_app/routes/scheduler_async.py')
if file_path.exists():
    mtime = os.path.getmtime(file_path)
    from datetime import datetime
    mod_time = datetime.fromtimestamp(mtime)
    print(f"scheduler_async.py 修改时间: {mod_time}")
    
    # 检查 __pycache__
    cache_dir = file_path.parent / '__pycache__'
    if cache_dir.exists():
        pyc_files = list(cache_dir.glob('scheduler_async*.pyc'))
        if pyc_files:
            for pyc in pyc_files:
                pyc_mtime = os.path.getmtime(pyc)
                pyc_time = datetime.fromtimestamp(pyc_mtime)
                print(f"  缓存文件: {pyc.name}")
                print(f"  缓存时间: {pyc_time}")
                if pyc_mtime < mtime:
                    print(f"  ⚠️  缓存过期！")
        else:
            print("  无缓存文件")

print("\n" + "=" * 70)
print("诊断完成")
print("=" * 70)
