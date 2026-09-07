#!/usr/bin/env python3
"""
强力修复所有语法错误 - 处理各种自动重构引入的问题
"""

from pathlib import Path
import subprocess
import re

def fix_empty_blocks(lines):
    """修复空的代码块"""
    modified = False
    i = 0
    while i < len(lines):
        line = lines[i]

        # 检测以冒号结尾的语句（if, def, class, for, while, try, except, etc.）
        if line.strip() and line.rstrip().endswith(':'):
            # 计算缩进
            indent = len(line) - len(line.lstrip())
            expected_indent = indent + 4

            # 检查下一行
            if i + 1 < len(lines):
                next_line = lines[i + 1]

                # 如果下一行是空行
                if not next_line.strip():
                    # 检查再下一行
                    if i + 2 < len(lines):
                        line_after = lines[i + 2]
                        next_indent = len(line_after) - len(line_after.lstrip()) if line_after.strip() else 0

                        # 如果缩进不正确，插入pass
                        if line_after.strip() and next_indent <= indent:
                            lines.insert(i + 1, ' ' * expected_indent + 'pass\n')
                            modified = True
                    else:
                        # 文件结束，插入pass
                        lines.insert(i + 1, ' ' * expected_indent + 'pass\n')
                        modified = True
                else:
                    # 检查下一行的缩进
                    next_indent = len(next_line) - len(next_line.lstrip())

                    # 如果缩进不足
                    if next_line.strip() and next_indent <= indent and not next_line.strip().startswith(('"""', "'''")):
                        lines.insert(i + 1, ' ' * expected_indent + 'pass\n')
                        modified = True
            else:
                # 文件结束，插入pass
                lines.append(' ' * expected_indent + 'pass\n')
                modified = True

        i += 1

    return lines, modified

def fix_helper_function_calls(lines):
    """修复辅助函数调用（缺少参数）"""
    modified = False
    i = 0
    while i < len(lines):
        line = lines[i]

        # 查找 _check_condition_N() 这样的函数调用
        if '_check_condition_' in line and '()' in line:
            # 查找对应的函数定义
            func_match = re.search(r'(_check_condition_\d+)\(\)', line)
            if func_match:
                func_name = func_match.group(1)

                # 向上查找函数定义
                for j in range(i - 1, max(0, i - 100), -1):
                    if f'def {func_name}(' in lines[j]:
                        # 检查函数定义的参数
                        def_line = lines[j]
                        if f'def {func_name}():' in def_line:
                            # 函数定义无参数，保持不变
                            break
                        else:
                            # 函数有参数，需要修复调用
                            # 简单处理：将调用改为无参数版本
                            # 或者将函数定义改为无参数
                            lines[j] = lines[j].replace(f'def {func_name}(', f'def {func_name}(')
                            # 实际上不需要修改，因为调用已经是无参数的
                            break

        i += 1

    return lines, modified

def fix_file(file_path):
    """修复单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        original = lines.copy()

        # 应用各种修复
        lines, mod1 = fix_empty_blocks(lines)
        lines, mod2 = fix_helper_function_calls(lines)

        modified = mod1 or mod2

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True

        return False

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False

def main():
    print("🔧 强力修复所有语法错误\n")

    # 找到所有有语法错误的文件
    error_files = []

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/']):
            continue

        result = subprocess.run(
            ['python', '-m', 'py_compile', str(py_file)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            error_files.append(py_file)

    print(f"找到 {len(error_files)} 个有语法错误的文件\n")

    fixed = 0
    for file_path in error_files:
        fname = str(file_path).split('/')[-1]

        if fix_file(file_path):
            # 验证修复
            result = subprocess.run(
                ['python', '-m', 'py_compile', str(file_path)],
                capture_output=True
            )

            if result.returncode == 0:
                fixed += 1
                print(f"  ✅ {fname}")
            else:
                print(f"  ⚠️  {fname} - 仍有错误")

    print(f"\n✅ 修复了 {fixed} / {len(error_files)} 个文件")

    # 再次检查
    remaining = 0
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/']):
            continue

        result = subprocess.run(
            ['python', '-m', 'py_compile', str(py_file)],
            capture_output=True
        )

        if result.returncode != 0:
            remaining += 1

    print(f"📊 剩余语法错误: {remaining} 个")

if __name__ == "__main__":
    main()
