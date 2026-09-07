#!/usr/bin/env python3
"""
修复接口导入路径
将 from adapters.outbound.repositories import I*Repository
改为 from domain.ports.repository_ports_extended import I*Repository
"""

import re
from pathlib import Path

FILES_TO_FIX = [
    'application/services/condition_monitor.py',
    'application/services/data_service_orm.py',
    'application/services/data_service.py',
    'application/services/decision_service.py',
]

def fix_file(file_path: str):
    """修复单个文件的导入路径"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  文件不存在: {file_path}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 替换导入路径
    content = content.replace(
        'from adapters.outbound.repositories import',
        'from domain.ports.repository_ports_extended import'
    )

    if content != original_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {file_path}")
        return True
    else:
        print(f"⏭️  {file_path} (无需修改)")
        return False

if __name__ == '__main__':
    print("修复接口导入路径...\n")

    fixed_count = 0
    for file_path in FILES_TO_FIX:
        if fix_file(file_path):
            fixed_count += 1

    print(f"\n修复完成: {fixed_count}/{len(FILES_TO_FIX)} 个文件")
