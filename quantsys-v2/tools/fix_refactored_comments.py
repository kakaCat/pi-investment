#!/usr/bin/env python3
"""
修复系统性重构工具引入的语法错误
"""

from pathlib import Path
import re

def fix_refactored_comments(file_path):
    """移除错误插入的 REFACTORED 注释"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified = False
        new_lines = []
        skip_until = -1

        for i, line in enumerate(lines):
            if i < skip_until:
                continue

            # 检测错误的 REFACTORED 注释模式

            new_lines.append(line)

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    print("🔧 修复 REFACTORED 注释引入的语法错误")
    print("=" * 80)

    fixed_count = 0
    error_count = 0

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv']):
            continue

        if fix_refactored_comments(py_file):
            fixed_count += 1
            print(f"✅ 修复: {py_file}")

    print("=" * 80)
    print(f"✅ 修复了 {fixed_count} 个文件")
    print("=" * 80)

    # 验证语法
    print("\n🔍 验证语法...")
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv']):
            continue

        try:
            import ast
            with open(py_file, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            error_count += 1
            if error_count <= 10:
                print(f"❌ {py_file}:{e.lineno}: {e.msg}")

    if error_count == 0:
        print("✅ 所有文件语法正确")
    else:
        print(f"❌ 仍有 {error_count} 个语法错误")

if __name__ == "__main__":
    main()
