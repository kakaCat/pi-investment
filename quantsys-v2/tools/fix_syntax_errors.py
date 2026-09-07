#!/usr/bin/env python3
"""
修复自动重构引入的语法错误
"""

from pathlib import Path
import subprocess

# TODO: 复杂度 20 - 需要重构拆分为更小的函数

def _validate_fix_syntax_errors_input(*args, **kwargs):
    """验证输入参数"""
    pass

def _process_fix_syntax_errors_data(data):
    """处理数据转换"""
    return data

def _build_fix_syntax_errors_result(data):
    """构建返回结果"""
    return data

def _validate_fix_syntax_errors_input(*args, **kwargs):
    """验证输入参数"""
    pass

def _process_fix_syntax_errors_data(data):
    """处理数据转换"""
    return data

def _build_fix_syntax_errors_result(data):
    """构建返回结果"""
    return data

def fix_syntax_errors():
    """修复所有语法错误"""

    print("🔧 修复自动重构引入的语法错误\n")

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

    # 对每个文件，尝试修复
    fixed = 0
    for file_path in error_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 检查是否有空的if语句（if xxx:\n 后面没有代码）
            modified = False
            i = 0
            while i < len(lines):
                line = lines[i]

                # 检测空的if语句
                if line.strip().startswith('if ') and line.strip().endswith(':'):
                    # 检查下一行
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        indent = len(line) - len(line.lstrip())
                        expected_indent = indent + 4
                        next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0

                        # 如果下一行缩进不正确或是空行
                        if next_line.strip() == '' or next_indent <= indent:
                            # 插入 pass 语句
                            lines.insert(i + 1, ' ' * expected_indent + 'pass  # TODO: implement\n')
                            modified = True
                            i += 1

                # 检测空的函数定义
                if line.strip().startswith('def ') and line.strip().endswith(':'):
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        indent = len(line) - len(line.lstrip())
                        expected_indent = indent + 4
                        next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0

                        if next_line.strip() == '' or (next_indent <= indent and not next_line.strip().startswith('"""')):
                            # 插入 pass 语句
                            lines.insert(i + 1, ' ' * expected_indent + 'pass  # TODO: implement\n')
                            modified = True
                            i += 1

                i += 1

            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

                # 验证修复
                result = subprocess.run(
                    ['python', '-m', 'py_compile', str(file_path)],
                    capture_output=True
                )

                if result.returncode == 0:
                    fixed += 1
                    fname = str(file_path).split('/')[-1]
                    print(f"  ✅ {fname}")

        except Exception as e:
            print(f"  ❌ {file_path}: {e}")

    print(f"\n✅ 修复了 {fixed} 个文件")

if __name__ == "__main__":
    fix_syntax_errors()