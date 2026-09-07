#!/usr/bin/env python3
"""直接测试 API 路由代码"""
import sys
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(Path('.env'))

# 导入路由函数
from adapters.inbound.fastapi_app.routes.scheduler_async import get_tasks
import asyncio

async def test():
    print("测试 get_tasks 函数...")
    try:
        result = await get_tasks(page=1, pageSize=12)
        print(f"\n结果:")
        print(f"  Success: {result.get('success')}")
        print(f"  Total: {result.get('data', {}).get('total')}")
        print(f"  Items: {len(result.get('data', {}).get('items', []))}")
        
        items = result.get('data', {}).get('items', [])
        if items:
            print(f"\n任务列表:")
            for item in items[:3]:
                print(f"  - {item.get('name')}")
        else:
            print("\n❌ 没有返回任务数据")
            
            # 调试：直接查询
            from infrastructure.persistence.orm.config import get_session
            from sqlalchemy import text
            session = get_session()
            count = session.execute(text("SELECT COUNT(*) FROM scheduler_tasks WHERE deleted_at IS NULL")).scalar()
            print(f"\n直接查询数据库: {count} 条记录")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
