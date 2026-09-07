#!/usr/bin/env python3
"""
最终代码质量报告 - 统计所有已修复的问题
"""

import ast
from pathlib import Path
from collections import defaultdict

def calc_complexity(node):
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

def count_magic_numbers(source: str) -> int:
    """统计魔法数字"""
    try:
        tree = ast.parse(source)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Num):
                val = node.n
                # 排除常见的非魔法数字
                if val not in (0, 1, -1, 2, 10, 100, 1000):
                    count += 1
        return count
    except:
        return 0

def main():
    print("📊 最终代码质量报告\n")
    print("=" * 60)

    # 统计各类问题
    high_complexity = []
    long_functions = []
    large_classes = []
    magic_numbers_total = 0
    syntax_errors = []

    total_files = 0
    total_functions = 0
    total_classes = 0

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'test_', 'tools/']):
            continue

        total_files += 1

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                source = f.read()

            # 检查语法错误
            try:
                tree = ast.parse(source)
            except SyntaxError as e:
                syntax_errors.append((py_file, e.lineno))
                continue

            # 统计魔法数字
            magic_numbers_total += count_magic_numbers(source)

            # 分析函数和类
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    c = calc_complexity(node)
                    if c > 15:
                        high_complexity.append((py_file, node.name, c))

                    # 计算函数行数
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        lines = node.end_lineno - node.lineno
                        if lines > 100:
                            long_functions.append((py_file, node.name, lines))

                elif isinstance(node, ast.ClassDef):
                    total_classes += 1
                    methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                    if len(methods) > 20:
                        large_classes.append((py_file, node.name, len(methods)))

        except Exception as e:
            continue

    # 输出报告
    print(f"\n📁 总文件数: {total_files}")
    print(f"🔧 总函数数: {total_functions}")
    print(f"📦 总类数: {total_classes}")

    print(f"\n{'='*60}")
    print("问题统计:")
    print(f"{'='*60}")

    # 语法错误
    if syntax_errors:
        print(f"\n❌ 语法错误: {len(syntax_errors)} 个")
        for fpath, lineno in syntax_errors[:5]:
            fname = str(fpath).split('/')[-1]
            print(f"  - {fname}:{lineno}")
    else:
        print(f"\n✅ 语法错误: 0 个")

    # 高复杂度函数
    print(f"\n🔴 高复杂度函数 (>15): {len(high_complexity)} 个")
    if high_complexity:
        print("  前10个最复杂的函数:")
        for fpath, fname, c in sorted(high_complexity, key=lambda x: -x[2])[:10]:
            file_short = str(fpath).split('/')[-1]
            print(f"    {file_short}:{fname} = {c}")

    # 长函数
    print(f"\n🟡 长函数 (>100行): {len(long_functions)} 个")
    if long_functions:
        print("  前5个最长的函数:")
        for fpath, fname, lines in sorted(long_functions, key=lambda x: -x[2])[:5]:
            file_short = str(fpath).split('/')[-1]
            print(f"    {file_short}:{fname} = {lines} 行")

    # 大类
    print(f"\n🟡 大类 (>20方法): {len(large_classes)} 个")
    if large_classes:
        for fpath, cname, methods in large_classes[:5]:
            file_short = str(fpath).split('/')[-1]
            print(f"    {file_short}:{cname} = {methods} 方法")

    # 魔法数字
    print(f"\n🟢 魔法数字: ~{magic_numbers_total} 个")

    # 总结
    print(f"\n{'='*60}")
    print("修复进度:")
    print(f"{'='*60}")

    initial_issues = 670  # 初始问题总数
    current_issues = len(syntax_errors) + len(high_complexity) + len(long_functions) + len(large_classes)

    fixed = initial_issues - current_issues
    progress = (fixed / initial_issues) * 100

    print(f"\n初始问题: {initial_issues} 个")
    print(f"当前问题: {current_issues} 个")
    print(f"已修复: {fixed} 个")
    print(f"完成度: {progress:.1f}%")

    if syntax_errors == 0:
        print(f"\n✅ 所有语法错误已修复！")

    if len(high_complexity) < 50:
        print(f"✅ 高复杂度函数从 164 减少到 {len(high_complexity)}")

    print(f"\n{'='*60}")
    print("建议后续行动:")
    print(f"{'='*60}")
    if high_complexity:
        print("1. 继续重构剩余的高复杂度函数")
        print("2. 优先处理复杂度 > 30 的函数")
    if long_functions:
        print("3. 拆分长函数 (>100行)")
    if large_classes:
        print("4. 重构大类 (>20方法)")
    if magic_numbers_total > 100:
        print("5. 提取魔法数字到常量")

    print("\n✅ 报告完成")

if __name__ == "__main__":
    main()
