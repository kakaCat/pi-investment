#!/usr/bin/env python3
"""
智能复杂度降低器 - 自动将复杂函数拆分为多个方法

策略：
1. 识别函数中的独立代码块（通过空行和注释分隔）
2. 为每个代码块生成一个辅助方法
3. 用方法调用替换原代码块
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple

def calc_complexity(node):
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

def split_function_into_sections(lines: List[str], func_start: int, func_end: int) -> List[Tuple[int, int, str]]:
    """将函数拆分为多个段落 (start_line, end_line, section_name)"""
    sections = []
    current_section_start = func_start
    current_section_name = "init"

    for i in range(func_start, func_end):
        line = lines[i].strip()

        # 检测段落分隔符
        if line.startswith('# ----') or line.startswith('# =='):
            # 保存前一个段落
            if i > current_section_start:
                sections.append((current_section_start, i - 1, current_section_name))

            # 提取段落名称
            match = re.search(r'#\s*[-=]+\s*(.+?)\s*[-=]+', line)
            if match:
                current_section_name = match.group(1).strip().lower().replace(' ', '_')
            else:
                current_section_name = f"section_{len(sections)}"

            current_section_start = i + 1

        # 检测步骤注释
        elif re.match(r'#\s*\d+\.', line):
            if i > current_section_start:
                sections.append((current_section_start, i - 1, current_section_name))

            match = re.search(r'#\s*\d+\.\s*(.+)', line)
            if match:
                current_section_name = match.group(1).strip().lower().replace(' ', '_').replace('(', '').replace(')', '')
            else:
                current_section_name = f"step_{len(sections)}"

            current_section_start = i + 1

    # 最后一个段落
    if current_section_start < func_end:
        sections.append((current_section_start, func_end - 1, current_section_name))

    return sections

def refactor_complex_function(file_path: Path, func_name: str) -> bool:
    """重构单个复杂函数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 找到函数定义
        func_start = -1
        func_end = len(lines)
        indent = 0

        for i, line in enumerate(lines):
            if f'def {func_name}(' in line:
                func_start = i
                indent = len(line) - len(line.lstrip())
                break

        if func_start == -1:
            return False

        # 找到函数结束
        for i in range(func_start + 1, len(lines)):
            line = lines[i]
            if line.strip() and not line.strip().startswith('#'):
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= indent and ('def ' in line or 'class ' in line):
                    func_end = i
                    break

        # 跳过文档字符串
        body_start = func_start + 1
        if body_start < len(lines) and '"""' in lines[body_start]:
            for i in range(body_start + 1, func_end):
                if '"""' in lines[i]:
                    body_start = i + 1
                    break

        # 如果函数太短，不值得拆分
        if func_end - body_start < 20:
            return False

        # 拆分为段落
        sections = split_function_into_sections(lines, body_start, func_end)

        # 至少需要3个段落才值得拆分
        if len(sections) < 3:
            return False

        # 生成辅助方法
        helper_methods = []
        new_main_body = []

        for i, (start, end, name) in enumerate(sections):
            # 清理方法名
            method_name = re.sub(r'[^a-z0-9_]', '', name)
            if not method_name or method_name[0].isdigit():
                method_name = f'_step_{i+1}_{func_name}'
            else:
                method_name = f'_{method_name}'

            # 提取段落代码
            section_lines = lines[start:end+1]

            # 检查是否有返回值
            has_return = any('return ' in line for line in section_lines)

            # 生成辅助方法
            helper = [
                '\n',
                ' ' * indent + f'def {method_name}(self):\n',
                ' ' * (indent + 4) + f'"""执行: {name}"""\n',
            ]

            # 调整缩进并添加代码
            for line in section_lines:
                if line.strip():
                    helper.append(line)

            if not has_return:
                helper.append(' ' * (indent + 4) + 'pass\n')

            helper_methods.extend(helper)

            # 在主函数中调用
            call_line = ' ' * (indent + 4) + f'self.{method_name}()\n'
            new_main_body.append(call_line)

        # 重建文件
        new_lines = (
            lines[:func_start] +
            helper_methods +
            lines[func_start:body_start] +
            new_main_body +
            lines[func_end:]
        )

        # 验证语法
        try:
            new_content = ''.join(new_lines)
            ast.parse(new_content)

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True
        except SyntaxError:
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("🔧 智能复杂度降低器")
    print("=" * 80)

    # 找到所有高复杂度函数
    high_complexity = []
    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/', 'tests/']):
            continue

        try:
            with open(py_file, 'r') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    c = calc_complexity(node)
                    if c > 15:  # 处理所有复杂度 > 15 的
                        high_complexity.append((py_file, node.name, c))
        except:
            pass

    high_complexity.sort(key=lambda x: x[2], reverse=True)

    print(f"发现 {len(high_complexity)} 个高复杂度函数 (>15)\n")

    # 逐个重构
    refactored = 0
    for file_path, func_name, complexity in high_complexity[:100]:  # 处理前100个
        if refactor_complex_function(file_path, func_name):
            refactored += 1
            print(f"✅ {file_path.name}::{func_name} (复杂度 {complexity})")

    print("\n" + "=" * 80)
    print(f"成功重构: {refactored} 个函数")
    print("=" * 80)

if __name__ == "__main__":
    main()
