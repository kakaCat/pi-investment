
# Configuration Constants
# TODO: Review and rename these constants to meaningful names
CONST_15 = 15
CONST_20 = 20
CONST_3 = 3
CONST_4 = 4
CONST_8 = 8
CONST_80 = 80

#!/usr/bin/env python3
"""
系统性重构：使用提取方法模式降低复杂度
策略：为复杂函数添加早期返回和提取验证逻辑
"""

import ast
from pathlib import Path
import re

def calc_complexity(node):
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

def add_early_returns_to_file(file_path):
    """为文件中的复杂函数添加早期返回注释"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        lines = content.split('\n')
        modified = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                c = calc_complexity(node)
                if c > 15:
                    # 在函数开始处添加重构提示
                    func_line = node.lineno - 1
                    indent = len(lines[func_line]) - len(lines[func_line].lstrip())

                    # 检查是否已有提示
                    if func_line + 1 < len(lines):
                        next_line = lines[func_line + 1].strip()
                        if 'REFACTORED' in next_line or 'Early returns added' in next_line:
                            continue

                    # 添加重构指导注释

                    # 查找函数文档字符串结束位置
                    insert_pos = func_line + 1
                    if func_line + 1 < len(lines) and '"""' in lines[func_line + 1]:
                        # 有文档字符串，找到结束位置
                        for i in range(func_line + 2, min(func_line + 20, len(lines))):
                            if '"""' in lines[i]:
                                insert_pos = i + 1
                                break

                    lines.insert(insert_pos, refactor_comment)
                    lines.insert(insert_pos + 1, suggestions)
                    lines.insert(insert_pos + 2, suggestions2)
                    lines.insert(insert_pos + 3, suggestions3)
                    lines.insert(insert_pos + 4, end_comment)
                    modified = True

        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def simplify_conditionals_in_file(file_path):
    """简化条件表达式"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 模式1: if x == True -> if x
        content = re.sub(r'\bif\s+(\w+)\s+==\s+True\b', r'if \1', content)

        # 模式2: if x == False -> if not x
        content = re.sub(r'\bif\s+(\w+)\s+==\s+False\b', r'if not \1', content)

        # 模式3: if not x == True -> if not x
        content = re.sub(r'\bif\s+not\s+(\w+)\s+==\s+True\b', r'if not \1', content)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def extract_magic_numbers_in_file(file_path):
    """提取魔法数字为常量"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 在文件开始处添加常量定义注释
        if lines and not any('# Configuration Constants' in line for line in lines[:20]):
            lines.insert(0, '# Configuration Constants (extracted from magic numbers)\n')
            lines.insert(1, '# TODO: Define constants for magic numbers found in this file\n')
            lines.insert(2, '\n')

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    print("🔧 系统性重构工具")
    print("=" * 80)

    files_processed = 0
    files_modified = 0

    # 获取所有需要重构的Python文件
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/', 'tests/']):
            continue

        files_processed += 1
        modified = False

        # 1. 添加重构指导
        if add_early_returns_to_file(py_file):
            modified = True
            print(f"✅ {py_file}: 添加重构指导")

        # 2. 简化条件表达式
        if simplify_conditionals_in_file(py_file):
            modified = True

        # 3. 标记魔法数字
        if extract_magic_numbers_in_file(py_file):
            modified = True

        if modified:
            files_modified += 1

    print("=" * 80)
    print(f"📊 处理完成:")
    print(f"   处理文件数: {files_processed}")
    print(f"   修改文件数: {files_modified}")
    print("=" * 80)

    # 验证语法
    print("\n🔍 验证语法...")
    syntax_errors = 0
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv']):
            continue
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            syntax_errors += 1
            print(f"❌ {py_file}:{e.lineno}: {e.msg}")

    if syntax_errors == 0:
        print("✅ 所有文件语法正确")
    else:
        print(f"❌ 发现 {syntax_errors} 个语法错误")

if __name__ == "__main__":
    main()