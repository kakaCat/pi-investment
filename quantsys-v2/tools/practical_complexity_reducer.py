#!/usr/bin/env python3
"""
实用复杂度降低器 - 通过自动重构模式实际降低复杂度

核心策略：
1. 合并连续的条件检查为单一验证函数
2. 提取独立的代码块为辅助方法
3. 将长函数按逻辑段落拆分
4. 简化布尔表达式
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple

def find_consecutive_guards(lines: List[str], start: int, indent: int) -> List[Tuple[int, int]]:
    """找到连续的守卫条件（参数校验）"""
    guards = []
    i = start

    while i < len(lines):
        line = lines[i].strip()

        # 空行或注释，跳过
        if not line or line.startswith('#'):
            i += 1
            continue

        # 检测守卫模式: if not/if 条件 + raise/return
        if line.startswith('if '):
            # 检查下一行是否是 raise 或 return
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('raise ') or next_line.startswith('return '):
                    guards.append((i, i + 1))
                    i += 2
                    continue

        # 不再是守卫模式，停止
        if len(guards) >= 2:  # 至少2个守卫才值得提取
            break
        else:
            guards = []

        i += 1

    return guards

def extract_guards_to_method(source_code: str, func_name: str) -> str:
    """将函数开头的连续守卫条件提取为验证方法"""
    lines = source_code.split('\n')

    # 找到函数定义
    func_line = -1
    for i, line in enumerate(lines):
        if f'def {func_name}(' in line:
            func_line = i
            break

    if func_line == -1:
        return source_code

    # 获取函数缩进
    indent = len(lines[func_line]) - len(lines[func_line].lstrip())

    # 跳过文档字符串
    body_start = func_line + 1
    if body_start < len(lines) and '"""' in lines[body_start]:
        for i in range(body_start + 1, len(lines)):
            if '"""' in lines[i]:
                body_start = i + 1
                break

    # 查找连续的守卫条件
    guards = find_consecutive_guards(lines, body_start, indent)

    if len(guards) < 2:
        return source_code

    # 提取守卫代码
    guard_lines = []
    for start, end in guards:
        guard_lines.extend(lines[start:end+1])

    # 生成验证方法
    validation_method = [
        '',
        ' ' * indent + f'def _validate_{func_name}_params(self, **kwargs):',
        ' ' * (indent + 4) + '"""参数验证"""',
    ]

    # 将守卫条件复制到验证方法中（调整缩进）
    for line in guard_lines:
        if line.strip():
            validation_method.append(' ' * (indent + 4) + line.strip())

    validation_method.append(' ' * (indent + 4) + 'return True')
    validation_method.append('')

    # 在原函数前插入验证方法
    new_lines = (lines[:func_line] +
                 validation_method +
                 lines[func_line:body_start])

    # 替换原函数中的守卫为单一调用
    call_line = ' ' * (indent + 4) + 'self._validate_' + func_name + '_params(**locals())'
    new_lines.append(call_line)

    # 保留守卫之后的代码
    if guards:
        last_guard_end = guards[-1][1]
        new_lines.extend(lines[last_guard_end + 1:])

    return '\n'.join(new_lines)

# TODO: 复杂度 22 - 需要重构拆分为更小的函数

def split_long_function_by_comments(source_code: str, func_name: str, max_lines: int = 100) -> str:
    """根据注释段落拆分长函数"""
    lines = source_code.split('\n')

    # 找到函数
    func_line = -1
    for i, line in enumerate(lines):
        if f'def {func_name}(' in line:
            func_line = i
            break

    if func_line == -1:
        return source_code

    # 找到函数结束（下一个def或class）
    func_end = len(lines)
    indent = len(lines[func_line]) - len(lines[func_line].lstrip())

    for i in range(func_line + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.strip().startswith('#'):
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= indent and ('def ' in line or 'class ' in line):
                func_end = i
                break

    func_length = func_end - func_line

    if func_length <= max_lines:
        return source_code

    # 查找逻辑段落（通过注释识别）
    sections = []
    current_section_start = func_line + 1

    for i in range(func_line + 1, func_end):
        line = lines[i].strip()
        # 检测段落注释: # ---- 或 # 1. 或 # Step
        if (line.startswith('# ----') or
            re.match(r'# \d+\.', line) or
            line.startswith('# Step')):
            if i > current_section_start:
                sections.append((current_section_start, i - 1))
            current_section_start = i

    # 最后一个段落
    if current_section_start < func_end:
        sections.append((current_section_start, func_end - 1))

    # 如果找到多个段落，生成辅助方法
    if len(sections) >= 3:
        new_methods = []

        for idx, (start, end) in enumerate(sections[1:], 1):  # 跳过第一段（通常是参数验证）
            method_name = f'_step{idx}_{func_name}'
            method_lines = [
                '',
                ' ' * indent + f'def {method_name}(self):',
                ' ' * (indent + 4) + f'"""执行步骤 {idx}"""',
            ]

            # 复制段落代码
            for line in lines[start:end+1]:
                if line.strip():
                    method_lines.append(line)

            new_methods.extend(method_lines)

        # 重构主函数
        main_func = lines[func_line:sections[0][1]+1]
        for idx in range(1, len(sections)):
            call = ' ' * (indent + 4) + f'self._step{idx}_{func_name}()'
            main_func.append(call)

        # 组合
        result = lines[:func_line] + main_func + new_methods + lines[func_end:]
        return '\n'.join(result)

    return source_code

def simplify_boolean_in_source(source_code: str) -> str:
    """简化源代码中的布尔表达式"""
    # if x == True -> if x
    source_code = re.sub(r'\bif\s+(\w+)\s+==\s+True\b', r'if \1', source_code)

    # if x == False -> if not x
    source_code = re.sub(r'\bif\s+(\w+)\s+==\s+False\b', r'if not \1', source_code)

    # if x is True -> if x
    source_code = re.sub(r'\bif\s+(\w+)\s+is\s+True\b', r'if \1', source_code)

    # if x is False -> if not x
    source_code = re.sub(r'\bif\s+(\w+)\s+is\s+False\b', r'if not \1', source_code)

    return source_code

def reduce_file_complexity(file_path: Path) -> Tuple[bool, int, int]:
    """降低文件复杂度，返回 (是否修改, 修改前复杂度, 修改后复杂度)"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_source = f.read()

        # 计算原始复杂度
        try:
            tree = ast.parse(original_source)
            original_complexity = sum(
                calc_complexity(node)
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            )
        except:
            return False, 0, 0

        # 应用转换
        source = original_source

        # 1. 简化布尔表达式
        source = simplify_boolean_in_source(source)

        # 2. 为高复杂度函数提取验证逻辑
        # 3. 拆分长函数
        # （这些需要更复杂的实现，暂时跳过）

        # 计算新复杂度
        try:
            new_tree = ast.parse(source)
            new_complexity = sum(
                calc_complexity(node)
                for node in ast.walk(new_tree)
                if isinstance(node, ast.FunctionDef)
            )
        except:
            return False, original_complexity, original_complexity

        # 如果有改进，写回
        if new_complexity < original_complexity:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(source)
            return True, original_complexity, new_complexity

        return False, original_complexity, new_complexity

    except Exception as e:
        return False, 0, 0

def calc_complexity(node):
    """计算圈复杂度"""
    c = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            c += 1
        elif isinstance(child, ast.BoolOp):
            c += len(child.values) - 1
    return c

def main():
    print("🔧 实用复杂度降低器")
    print("=" * 80)

    total_files = 0
    improved_files = 0
    total_reduction = 0

    for py_file in Path('.').rglob('*.py'):
        if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'tools/', 'tests/']):
            continue

        total_files += 1
        modified, before, after = reduce_file_complexity(py_file)

        if modified:
            improved_files += 1
            reduction = before - after
            total_reduction += reduction
            print(f"✅ {py_file.name}: {before} -> {after} (-{reduction})")

    print("\n" + "=" * 80)
    print(f"处理文件: {total_files}")
    print(f"改进文件: {improved_files}")
    print(f"总复杂度降低: {total_reduction}")
    print("=" * 80)

if __name__ == "__main__":
    main()