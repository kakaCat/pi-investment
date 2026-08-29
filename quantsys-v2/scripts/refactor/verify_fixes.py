#!/usr/bin/env python3
"""快速验证脚本 - 验证所有中等问题的修复状态

Usage:
    python scripts/refactor/verify_fixes.py
    python scripts/refactor/verify_fixes.py --detailed
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

def check_sys_path_inserts(root: Path) -> Tuple[bool, int]:
    """检查 sys.path.insert 使用"""
    count = 0
    for py_file in root.rglob('*.py'):
        if any(part in {'venv', '__pycache__', '.git'} for part in py_file.parts):
            continue
        try:
            content = py_file.read_text(encoding='utf-8')
            count += content.count('sys.path.insert(')
        except:
            pass
    
    return count == 0, count

def check_direct_imports(root: Path) -> Tuple[bool, int]:
    """检查直接导入数据源"""
    import re
    count = 0
    forbidden = ['akshare', 'tushare', 'yfinance', 'baostock']
    allowed_dirs = {'adapters/outbound/datasources', 'tests'}
    
    for py_file in root.rglob('*.py'):
        if any(part in {'venv', '__pycache__', '.git'} for part in py_file.parts):
            continue
        
        # 检查是否在允许目录
        rel_path = str(py_file.relative_to(root))
        if any(rel_path.startswith(allowed) for allowed in allowed_dirs):
            continue
        
        try:
            content = py_file.read_text(encoding='utf-8')
            for lib in forbidden:
                if re.search(rf'^import\s+{lib}', content, re.MULTILINE):
                    count += 1
                if re.search(rf'^from\s+{lib}', content, re.MULTILINE):
                    count += 1
        except:
            pass
    
    return count == 0, count

def check_logging_unified(root: Path) -> Tuple[bool, Dict[str, int]]:
    """检查日志系统统一性"""
    import re
    stats = {'print': 0, 'logging': 0, 'structlog': 0}
    
    for py_file in root.rglob('*.py'):
        if any(part in {'venv', '__pycache__', '.git', 'tests'} for part in py_file.parts):
            continue
        
        try:
            content = py_file.read_text(encoding='utf-8')
            
            # 统计 print() 调试语句 (排除注释)
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('#'):
                    continue
                if re.search(r'\bprint\s*\(', line):
                    stats['print'] += 1
            
            # 统计导入
            if 'import logging' in content or 'from logging import' in content:
                stats['logging'] += 1
            if 'import structlog' in content or 'from structlog import' in content:
                stats['structlog'] += 1
        except:
            pass
    
    # 理想状态: 零 print，大部分使用 structlog
    return stats['print'] == 0, stats

def check_thread_management(root: Path) -> Tuple[bool, int]:
    """检查线程管理"""
    import re
    direct_thread_count = 0
    
    for py_file in root.rglob('*.py'):
        if any(part in {'venv', '__pycache__', '.git', 'tests', 'infrastructure/threading'} for part in py_file.parts):
            continue
        
        try:
            content = py_file.read_text(encoding='utf-8')
            # 查找直接创建线程 (不通过 ThreadManager)
            if re.search(r'threading\.Thread\(', content):
                direct_thread_count += 1
        except:
            pass
    
    return direct_thread_count == 0, direct_thread_count

def check_pyproject_exists(root: Path) -> bool:
    """检查 pyproject.toml 是否存在"""
    return (root / 'pyproject.toml').exists()

def verify_all(root: Path, detailed: bool = False) -> Dict:
    """验证所有问题"""
    results = {}
    
    print("🔍 验证中等问题修复状态...\n")
    print("=" * 60)
    
    # 问题 3: sys.path.insert
    passed, count = check_sys_path_inserts(root)
    results['sys_path'] = passed
    status = "✅ PASS" if passed else f"❌ FAIL ({count} 处)"
    print(f"问题 3: sys.path.insert 清理        {status}")
    
    # 问题 2: 直接导入数据源
    passed, count = check_direct_imports(root)
    results['direct_imports'] = passed
    status = "✅ PASS" if passed else f"❌ FAIL ({count} 处)"
    print(f"问题 2: 数据源直接导入清理        {status}")
    
    # 问题 4: 日志系统统一
    passed, stats = check_logging_unified(root)
    results['logging'] = passed
    status = "✅ PASS" if passed else f"⚠️  PARTIAL (print: {stats['print']}, logging: {stats['logging']}, structlog: {stats['structlog']})"
    print(f"问题 4: 日志系统统一              {status}")
    
    # 问题 5: 线程管理
    passed, count = check_thread_management(root)
    results['threading'] = passed
    status = "✅ PASS" if passed else f"⚠️  PARTIAL ({count} 处直接创建)"
    print(f"问题 5: 线程统一管理              {status}")
    
    # 问题 3: pyproject.toml
    passed = check_pyproject_exists(root)
    results['pyproject'] = passed
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"问题 3: pyproject.toml 存在       {status}")
    
    print("=" * 60)
    
    # 总结
    total = len(results)
    passed_count = sum(1 for v in results.values() if v)
    print(f"\n📊 总结: {passed_count}/{total} 项通过")
    
    if passed_count == total:
        print("🎉 所有中等问题已修复！")
        return_code = 0
    elif passed_count >= total * 0.7:
        print("⚠️  大部分问题已修复，仍有少量待处理")
        return_code = 1
    else:
        print("❌ 仍有较多问题待修复")
        return_code = 2
    
    print("\n💡 下一步:")
    if not results.get('sys_path'):
        print("  - 运行: python scripts/refactor/remove_sys_path_hacks.py --fix")
    if not results.get('direct_imports'):
        print("  - 运行: python scripts/refactor/find_direct_imports.py")
    if not results.get('pyproject'):
        print("  - pyproject.toml 已创建，运行: pip install -e .")
    
    return return_code

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='验证中等问题修复状态')
    parser.add_argument('--detailed', action='store_true',
                        help='显示详细信息')
    parser.add_argument('--root', type=Path, default=Path('.'),
                        help='项目根目录')
    
    args = parser.parse_args()
    
    return_code = verify_all(args.root, args.detailed)
    sys.exit(return_code)

if __name__ == '__main__':
    main()
