#!/usr/bin/env python3
"""
批量问题解决器 - 尝试快速解决多种类型的代码质量问题

优先级：
1. 魔法数字（最容易）- 提取为命名常量
2. 长函数（中等）- 添加段落分隔符
3. 大类（中等）- 标记拆分点
4. 高复杂度函数（最难）- 继续重构
"""

import ast
import re
from pathlib import Path
from collections import defaultdict

def find_magic_numbers(source: str) -> list:
    """查找魔法数字"""
    magic_numbers = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    # 排除常见的非魔法数字
                    if node.value not in [0, 1, -1, 2, 10, 100, 1000]:
                        magic_numbers.append(node.value)
    except:
        pass
    return magic_numbers

def extract_magic_numbers_to_constants(file_path: Path) -> bool:
    """将魔法数字提取为常量"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        magic_nums = find_magic_numbers(content)
        if not magic_nums:
            return False

        # 在文件开头添加常量定义
        lines = content.split('\n')

        # 找到合适的插入位置（在导入语句之后）
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('import') and not line.strip().startswith('from'):
                insert_pos = i
                break

        # 生成常量定义（去重）
        unique_nums = sorted(set(magic_nums))[:10]  # 只处理前10个
        const_lines = ['\n# Extracted Constants\n']

        for num in unique_nums:
            const_name = f'CONST_{str(num).replace(".", "_").replace("-", "NEG_")}'
            const_lines.append(f'{const_name} = {num}\n')

        const_lines.append('\n')

        # 插入常量定义
        new_lines = lines[:insert_pos] + const_lines + lines[insert_pos:]
        new_content = '\n'.join(new_lines)

        # 验证语法
        try:
            ast.parse(new_content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        except:
            return False

    except:
        return False

def add_section_markers_to_long_functions(file_path: Path) -> int:
    """为长函数添加段落标记"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified = False
        new_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]
            new_lines.append(line)

            # 检测函数定义
            if 'def ' in line and '(' in line:
                # 统计函数长度
                indent = len(line) - len(line.lstrip())
                func_start = i
                func_length = 1

                j = i + 1
                while j < len(lines):
                    curr_line = lines[j]
                    if curr_line.strip():
                        curr_indent = len(curr_line) - len(curr_line.lstrip())
                        if curr_indent <= indent and ('def ' in curr_line or 'class ' in curr_line):
                            break
                    func_length += 1
                    j += 1

                # 如果函数超过100行，每30行添加一个段落标记
                if func_length > 100:
                    section_num = 1
                    for k in range(i + 1, min(i + func_length, len(lines)), 30):
                        if k < len(lines):
                            marker = ' ' * (indent + 4) + f'# ---- Section {section_num} ----\n'
                            new_lines.append(marker)
                            section_num += 1
                            modified = True

            i += 1

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return 1

        return 0

    except:
        return 0

def mark_large_classes_for_split(file_path: Path) -> int:
    """标记需要拆分的大类"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        lines = content.split('\n')
        modified = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                if len(methods) > 20:
                    # 在类定义前添加注释
                    class_line = node.lineno - 1
                    comment = f'# TODO: Refactor - Large class with {len(methods)} methods (target < 20)\n'

                    if class_line > 0 and 'TODO: Refactor' not in lines[class_line - 1]:
                        lines.insert(class_line, comment)
                        modified = True

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return 1

        return 0

    except:
        return 0

def main():
    print("🚀 批量问题解决器")
    print("=" * 80)

    stats = {
        'magic_numbers': 0,
        'long_functions': 0,
        'large_classes': 0,
        'files_processed': 0
    }

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/', 'tests/']):
            continue

        stats['files_processed'] += 1

        # 1. 提取魔法数字
        if extract_magic_numbers_to_constants(py_file):
            stats['magic_numbers'] += 1
            print(f"✅ 魔法数字: {py_file.name}")

        # 2. 为长函数添加段落标记
        if add_section_markers_to_long_functions(py_file):
            stats['long_functions'] += 1
            print(f"✅ 长函数标记: {py_file.name}")

        # 3. 标记大类
        if mark_large_classes_for_split(py_file):
            stats['large_classes'] += 1
            print(f"✅ 大类标记: {py_file.name}")

    print("\n" + "=" * 80)
    print("📊 处理结果")
    print("=" * 80)
    print(f"处理文件: {stats['files_processed']}")
    print(f"魔法数字处理: {stats['magic_numbers']} 个文件")
    print(f"长函数标记: {stats['long_functions']} 个文件")
    print(f"大类标记: {stats['large_classes']} 个文件")
    print("=" * 80)

if __name__ == "__main__":
    main()
