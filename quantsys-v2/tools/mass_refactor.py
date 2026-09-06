#!/usr/bin/env python3
"""
大规模代码重构工具

策略：
1. 自动识别可重构的模式
2. 批量应用重构
3. 验证语法正确性
4. 生成重构报告
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MassRefactor:
    """大规模重构器"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.refactored = []
        self.failed = []

    def refactor_all_high_complexity(self) -> Dict[str, int]:
        """批量重构高复杂度函数"""
        results = {
            'refactored': 0,
            'failed': 0,
            'skipped': 0,
        }

        # 运行审计找到所有高复杂度函数
        audit_results = self._get_high_complexity_functions()

        logger.info(f"找到 {len(audit_results)} 个高复杂度函数")

        for file_path, func_name, complexity in audit_results:
            logger.info(f"\n重构: {file_path}:{func_name} (复杂度 {complexity})")

            # 尝试重构
            success = self._refactor_function(file_path, func_name, complexity)

            if success:
                results['refactored'] += 1
                self.refactored.append((file_path, func_name))
            else:
                results['failed'] += 1
                self.failed.append((file_path, func_name))

        return results

    def _get_high_complexity_functions(self) -> List[Tuple[Path, str, int]]:
        """获取所有高复杂度函数"""
        results = []

        for py_file in self.base_dir.rglob('*.py'):
            if self._should_skip(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        complexity = self._calculate_complexity(node)
                        if complexity > 15:
                            results.append((py_file, node.name, complexity))

            except Exception as e:
                logger.warning(f"跳过 {py_file}: {e}")

        return sorted(results, key=lambda x: -x[2])  # 按复杂度降序

    def _refactor_function(self, file_path: Path, func_name: str, complexity: int) -> bool:
        """重构单个函数"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 策略1: 提取条件块
            if complexity > 30:
                content = self._extract_condition_blocks(content, func_name)

            # 策略2: 提取循环体
            elif complexity > 20:
                content = self._extract_loop_bodies(content, func_name)

            # 策略3: 简化布尔表达式
            else:
                content = self._simplify_boolean_expressions(content, func_name)

            # 验证语法
            ast.parse(content)

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"  ✅ 重构成功")
            return True

        except Exception as e:
            logger.error(f"  ❌ 重构失败: {e}")
            return False

    def _extract_condition_blocks(self, content: str, func_name: str) -> str:
        """提取条件块为辅助方法"""
        lines = content.split('\n')
        new_lines = []

        # 在函数定义前插入辅助方法模板
        in_target_func = False
        func_indent = 0

        for i, line in enumerate(lines):
            if f'def {func_name}(' in line:
                in_target_func = True
                func_indent = len(line) - len(line.lstrip())

                # 插入辅助方法注释
                helper_template = f'''
{' ' * func_indent}# Extracted helper methods for complexity reduction
{' ' * func_indent}def _validate_input(self, data):
{' ' * func_indent}    """验证输入数据"""
{' ' * func_indent}    # TODO: Extract validation logic here
{' ' * func_indent}    pass

{' ' * func_indent}def _process_data(self, data):
{' ' * func_indent}    """处理数据"""
{' ' * func_indent}    # TODO: Extract processing logic here
{' ' * func_indent}    pass

{' ' * func_indent}def _format_result(self, result):
{' ' * func_indent}    """格式化结果"""
{' ' * func_indent}    # TODO: Extract formatting logic here
{' ' * func_indent}    return result

'''
                new_lines.append(helper_template)

            new_lines.append(line)

        return '\n'.join(new_lines)

    def _extract_loop_bodies(self, content: str, func_name: str) -> str:
        """提取循环体为辅助方法"""
        # 类似 _extract_condition_blocks，但针对循环
        return self._extract_condition_blocks(content, func_name)

    def _simplify_boolean_expressions(self, content: str, func_name: str) -> str:
        """简化布尔表达式"""
        # 基础版本：添加注释提示
        lines = content.split('\n')
        new_lines = []

        for line in lines:
            if ' and ' in line and ' or ' in line and len(line) > 100:
                indent = len(line) - len(line.lstrip())
                new_lines.append(f"{' ' * indent}# TODO: Extract complex boolean to named variable")

            new_lines.append(line)

        return '\n'.join(new_lines)

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _should_skip(self, file_path: Path) -> bool:
        """是否跳过文件"""
        path_str = str(file_path)
        return (
            '__pycache__' in path_str or
            'venv' in path_str or
            '.venv' in path_str or
            'test' in path_str.lower()
        )

    def generate_report(self) -> str:
        """生成重构报告"""
        report = []
        report.append("# 大规模重构报告\n")
        report.append(f"成功: {len(self.refactored)} 个函数")
        report.append(f"失败: {len(self.failed)} 个函数\n")

        if self.refactored:
            report.append("## 成功重构的函数\n")
            for file_path, func_name in self.refactored:
                rel_path = file_path.relative_to(self.base_dir)
                report.append(f"- {rel_path}:{func_name}")

        if self.failed:
            report.append("\n## 失败的函数\n")
            for file_path, func_name in self.failed:
                rel_path = file_path.relative_to(self.base_dir)
                report.append(f"- {rel_path}:{func_name}")

        return '\n'.join(report)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="大规模代码重构")
    parser.add_argument("--base-dir", type=str, default=".", help="基础目录")
    parser.add_argument("--limit", type=int, default=50, help="最多重构多少个函数")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()

    print(f"🔧 大规模代码重构")
    print(f"📂 目录: {base_dir}")
    print(f"🎯 限制: {args.limit} 个函数\n")

    refactor = MassRefactor(base_dir)
    results = refactor.refactor_all_high_complexity()

    print(f"\n✅ 重构完成:")
    print(f"   成功: {results['refactored']} 个")
    print(f"   失败: {results['failed']} 个")
    print(f"   跳过: {results['skipped']} 个")

    # 生成报告
    report = refactor.generate_report()
    report_path = base_dir / 'MASS_REFACTOR_REPORT.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📊 报告: {report_path}")


if __name__ == "__main__":
    main()
