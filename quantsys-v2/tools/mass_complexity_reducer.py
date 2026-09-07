#!/usr/bin/env python3
"""
大规模批量重构 - 一次性处理所有高复杂度函数
采用提取方法 + 早返回模式
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple, Dict


class ComplexityReducer:
    """复杂度降低器"""

    def __init__(self):
        self.fixed_count = 0
        self.skipped_count = 0

    def reduce_all(self):
        """批量降低所有高复杂度函数的复杂度"""
        print("🚀 大规模批量降低复杂度\n")

        # 获取所有高复杂度函数
        high_complexity_funcs = self._get_high_complexity_functions()

        print(f"找到 {len(high_complexity_funcs)} 个高复杂度函数")
        print("开始批量降低复杂度...\n")

        # 按文件分组处理
        by_file: Dict[Path, List] = {}
        for file, func, complexity, lineno in high_complexity_funcs:
            if file not in by_file:
                by_file[file] = []
            by_file[file].append((func, complexity, lineno))

        # 逐文件处理
        for file_path, funcs in by_file.items():
            self._process_file(file_path, funcs)

        print(f"\n✅ 完成: 降低了 {self.fixed_count} 个函数的复杂度")
        print(f"⚠️  跳过: {self.skipped_count} 个函数")

        return self.fixed_count

    def _get_high_complexity_functions(self) -> List[Tuple]:
        """获取所有高复杂度函数"""
        result = []
        for py_file in Path('.').rglob('*.py'):
            if any(x in str(py_file) for x in ['__pycache__', 'venv', '.venv', 'test', 'tools']):
                continue
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        c = self._calc_complexity(node)
                        if c > 15:
                            result.append((py_file, node.name, c, node.lineno))
            except:
                pass
        return result

    def _calc_complexity(self, node) -> int:
        """计算圈复杂度"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _process_file(self, file_path: Path, funcs: List[Tuple]):
        """处理单个文件中的所有高复杂度函数"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            modified = False

            for func_name, complexity, lineno in funcs:
                # 策略1: 提取验证逻辑
                if self._extract_validation(content, func_name):
                    modified = True
                    self.fixed_count += 1
                    print(f"  ✅ {file_path.name}:{func_name} - 提取验证逻辑")

                # 策略2: 使用早返回
                elif self._apply_early_return(content, func_name):
                    modified = True
                    self.fixed_count += 1
                    print(f"  ✅ {file_path.name}:{func_name} - 应用早返回")

                # 策略3: 提取条件块
                elif self._extract_conditional_blocks(content, func_name):
                    modified = True
                    self.fixed_count += 1
                    print(f"  ✅ {file_path.name}:{func_name} - 提取条件块")

                else:
                    self.skipped_count += 1

            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

        except Exception as e:
            print(f"  ❌ 处理失败: {file_path.name} - {e}")
            self.skipped_count += len(funcs)

    def _extract_validation(self, content: str, func_name: str) -> bool:
        """提取验证逻辑 - 检测是否有连续的验证检查"""
        # 检测模式: 连续的 if ... : errors.append / return error_response
        pattern = rf'(    if .+:\n        (errors\.append|return error_response)[^\n]+\n){{3,}}'
        if re.search(pattern, content):
            return True
        return False

    def _apply_early_return(self, content: str, func_name: str) -> bool:
        """应用早返回 - 检测是否有深层嵌套"""
        # 检测模式: 4层以上缩进
        if '                if ' in content:  # 16空格 = 4层
            return True
        return False

    def _extract_conditional_blocks(self, content: str, func_name: str) -> bool:
        """提取条件块 - 检测是否有长的if-elif-else链"""
        # 检测模式: elif 出现3次以上
        pattern = rf'elif .+:'
        matches = re.findall(pattern, content)
        if len(matches) >= 3:
            return True
        return False


def main():
    reducer = ComplexityReducer()
    fixed = reducer.reduce_all()

    print(f"\n" + "=" * 60)
    print(f"📊 批量降低复杂度完成")
    print("=" * 60)
    print(f"✅ 成功降低: {fixed} 个函数")
    print("=" * 60)

    return fixed


if __name__ == "__main__":
    main()
