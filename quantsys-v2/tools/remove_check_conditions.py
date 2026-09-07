#!/usr/bin/env python3
"""
批量移除错误的 _check_condition_ 函数调用
"""

import re
from pathlib import Path
import subprocess

def fix_check_condition_errors(file_path):
    """移除错误插入的 _check_condition_ 调用"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # 模式1: 移除单独一行的 if _check_condition_N():
        # 这些通常是错误插入的
        content = re.sub(r'\n\s+if _check_condition_\d+\(\):\n', '\n', content)

        # 模式2: 移除空的 try: pass 块后面的 if _check_condition
        content = re.sub(
            r'try:\s+pass\s+if _check_condition_\d+\(\):',
            'try:',
            content
        )

        # 模式3: 移除错误缩进的 pass 语句
        lines = content.split('\n')
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # 检查是否是函数定义后紧跟pass
            if i > 0 and 'def ' in lines[i-1] and line.strip() == 'pass':
                # 检查下一行是否有实际代码
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # 如果下一行有实际代码，跳过这个pass
                    if next_line.strip() and not next_line.strip().startswith(('"""', "'''", '#')):
                        i += 1
                        continue

            new_lines.append(line)
            i += 1

        content = '\n'.join(new_lines)

        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"  ❌ 处理失败 {file_path}: {e}")
        return False

def main():
    print("🔧 批量移除错误的 _check_condition_ 调用\n")

    # 找到所有有语法错误的文件
    error_files = []
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/']):
            continue

        result = subprocess.run(['python', '-m', 'py_compile', str(py_file)],
                              capture_output=True, text=True)
        if result.returncode != 0:
            error_files.append(py_file)

    print(f"找到 {len(error_files)} 个有语法错误的文件\n")

    fixed = 0
    for file_path in error_files:
        fname = str(file_path).split('/')[-1]

        if fix_check_condition_errors(file_path):
            # 验证修复
            result = subprocess.run(['python', '-m', 'py_compile', str(file_path)],
                                  capture_output=True)

            if result.returncode == 0:
                fixed += 1
                print(f"  ✅ {fname}")
            else:
                print(f"  ⚠️  {fname} - 需要手动修复")

    print(f"\n✅ 自动修复了 {fixed} / {len(error_files)} 个文件")

    # 统计剩余错误
    remaining = 0
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/']):
            continue

        result = subprocess.run(['python', '-m', 'py_compile', str(py_file)],
                              capture_output=True)
        if result.returncode != 0:
            remaining += 1

    print(f"📊 剩余语法错误: {remaining} 个")

if __name__ == "__main__":
    main()
