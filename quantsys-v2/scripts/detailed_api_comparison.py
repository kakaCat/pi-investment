#!/usr/bin/env python3
"""详细对比 Flask 和 FastAPI 的 API 实现"""
import os
from pathlib import Path

print("=" * 70)
print("Flask vs FastAPI API 详细对比")
print("=" * 70)

# 1. 获取 Flask 路由列表
flask_backup = Path("archived/flask_backup_20260629_152409/api/routes")
flask_routes = set()
if flask_backup.exists():
    for f in flask_backup.glob("*.py"):
        if f.name != "__init__.py":
            flask_routes.add(f.stem)

# 2. 获取 FastAPI 路由列表
fastapi_dir = Path("adapters/inbound/fastapi_app/routes")
fastapi_routes = set()
if fastapi_dir.exists():
    for f in fastapi_dir.glob("*_async.py"):
        route_name = f.stem.replace("_async", "")
        fastapi_routes.add(route_name)

print(f"\n统计:")
print(f"  Flask 路由数: {len(flask_routes)}")
print(f"  FastAPI 路由数: {len(fastapi_routes)}")

# 3. 找出差异
missing_in_fastapi = flask_routes - fastapi_routes
extra_in_fastapi = fastapi_routes - flask_routes
common = flask_routes & fastapi_routes

print(f"\n✅ 两者都有: {len(common)}")
print(f"❌ Flask 有但 FastAPI 缺失: {len(missing_in_fastapi)}")
print(f"➕ FastAPI 新增: {len(extra_in_fastapi)}")

if missing_in_fastapi:
    print(f"\n❌ FastAPI 缺失的路由 ({len(missing_in_fastapi)} 个):")
    for route in sorted(missing_in_fastapi):
        print(f"  - {route}")

if extra_in_fastapi:
    print(f"\n➕ FastAPI 新增的路由 ({len(extra_in_fastapi)} 个):")
    for route in sorted(extra_in_fastapi):
        print(f"  - {route}")

print(f"\n✅ 已迁移的路由 ({len(common)} 个):")
for route in sorted(common):
    print(f"  - {route}")

# 4. 计算完成度
if flask_routes:
    completion = (len(common) / len(flask_routes)) * 100
    print(f"\n" + "=" * 70)
    print(f"迁移完成度: {completion:.1f}%")
    print(f"  已迁移: {len(common)}/{len(flask_routes)}")
    if missing_in_fastapi:
        print(f"  缺失: {len(missing_in_fastapi)}")
    print("=" * 70)
else:
    print("\n⚠️  无法计算完成度（Flask 备份不存在）")

# 5. 检查实现质量
print(f"\n检查 FastAPI 实现质量:")
print("-" * 70)

issues = []
for route in sorted(common):
    fastapi_file = fastapi_dir / f"{route}_async.py"
    if fastapi_file.exists():
        content = fastapi_file.read_text()
        
        # 检查是否只是模板代码
        has_todo = "TODO" in content
        has_template = "自动生成" in content or "template" in content.lower()
        is_small = len(content) < 1000
        
        if has_todo and is_small:
            issues.append(f"  ⚠️  {route}: 可能只是模板（有 TODO，文件较小）")

if issues:
    print(f"\n发现 {len(issues)} 个可能的问题:")
    for issue in issues[:10]:  # 只显示前10个
        print(issue)
    if len(issues) > 10:
        print(f"  ... 还有 {len(issues) - 10} 个")
else:
    print("  ✅ 未发现明显问题")

print("\n" + "=" * 70)
