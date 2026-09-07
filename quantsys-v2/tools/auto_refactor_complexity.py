#!/usr/bin/env python3
"""
自动降低复杂度 - 系统性地重构所有高复杂度函数
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple, Set

def calc_complexity(node):
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

def extract_validation_block(func_body: List) -> Tuple[List, List]:
    """从函数体中提取验证代码块"""
    validation_stmts = []
    remaining_stmts = []

    for stmt in func_body:
        # 检查是否是验证语句（包含 return 或 raise 的 if 语句）
        is_validation = False
        if isinstance(stmt, ast.If):
            for node in ast.walk(stmt):
                if isinstance(node, (ast.Return, ast.Raise)):
                    is_validation = True
                    break

        if is_validation and len(validation_stmts) < 5:  # 只提取前5个验证
            validation_stmts.append(stmt)
        else:
            remaining_stmts.append(stmt)

    return validation_stmts, remaining_stmts

def generate_helper_functions(func_node: ast.FunctionDef) -> str:
    """为高复杂度函数生成辅助函数"""
    func_name = func_node.name

    # 分析函数体，识别可提取的部分
    validation_stmts, _ = extract_validation_block(func_node.body)

    helpers = []

    # 生成验证函数
    if validation_stmts:
        helper_code = f'''
def _validate_{func_name}_input(data):
    """验证输入参数"""
    # TODO: 将验证逻辑移到这里
    return True, None
'''
        helpers.append(helper_code)

    # 生成数据处理函数
    helper_code = f'''
def _process_{func_name}_data(data):
    """处理数据转换"""
    # TODO: 将数据处理逻辑移到这里
    return data
'''
    helpers.append(helper_code)

    # 生成结果构建函数
    helper_code = f'''
def _build_{func_name}_result(result):
    """构建返回结果"""
    # TODO: 将结果构建逻辑移到这里
    return result
'''
    helpers.append(helper_code)

    return '\n'.join(helpers)

def refactor_high_complexity_function(file_path: Path, func_name: str, complexity: int) -> bool:
    """重构单个高复杂度函数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
            lines = source.split('\n')

        tree = ast.parse(source)

        # 找到目标函数
        target_func = None
        func_lineno = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                target_func = node
                func_lineno = node.lineno - 1
                break

        if not target_func:
            return False

        # 在函数前插入辅助函数（如果还没有）
        helper_funcs = generate_helper_functions(target_func)

        # 检查是否已经有辅助函数
        if f'_validate_{func_name}_input' in source:
            return False  # 已经处理过

        # 在函数定义前插入辅助函数
        # 找到函数定义前的最近的空行或类定义
        insert_line = func_lineno
        while insert_line > 0 and lines[insert_line - 1].strip():
            insert_line -= 1

        # 插入辅助函数
        helper_lines = helper_funcs.strip().split('\n')
        lines[insert_line:insert_line] = helper_lines + ['']

        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return True

    except Exception as e:
        print(f"  ❌ 重构失败: {e}")
        return False

def main():
    print("🚀 自动降低复杂度 - 批量重构\n")

    # 获取所有高复杂度函数
    high_complexity = []
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'test_', 'tools/']):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    c = calc_complexity(node)
                    if c > 15:
                        high_complexity.append((py_file, node.name, c))
        except:
            continue

    # 按复杂度排序
    high_complexity.sort(key=lambda x: -x[2])

    print(f"找到 {len(high_complexity)} 个高复杂度函数")
    print("开始批量重构...\n")

    refactored = 0
    for file_path, func_name, complexity in high_complexity[:50]:  # 处理前50个
        fname = str(file_path).split('/')[-1]
        print(f"  🔧 {fname}:{func_name} (复杂度 {complexity})")

        if refactor_high_complexity_function(file_path, func_name, complexity):
            refactored += 1
            print(f"    ✅ 已添加辅助函数框架")

    print(f"\n✅ 为 {refactored} 个函数生成了辅助函数框架")
    print("📝 下一步：手动填充辅助函数的实现")

if __name__ == "__main__":
    main()
