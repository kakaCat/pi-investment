"""
批量复杂度降低工具

自动识别和重构高复杂度函数的工具
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ComplexityIssue:
    """复杂度问题"""
    function_name: str
    complexity: int
    file: Path
    line: int
    suggestions: List[str]


class ComplexityAnalyzer:
    """复杂度分析器"""

    def __init__(self):
        self.issues: List[ComplexityIssue] = []

    def analyze_function(self, node: ast.FunctionDef, file_path: Path) -> Optional[ComplexityIssue]:
        """分析函数复杂度并给出建议"""
        complexity = self._calculate_complexity(node)

        if complexity <= 15:
            return None

        suggestions = self._generate_suggestions(node, complexity)

        return ComplexityIssue(
            function_name=node.name,
            complexity=complexity,
            file=file_path,
            line=node.lineno,
            suggestions=suggestions
        )

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _generate_suggestions(self, node: ast.FunctionDef, complexity: int) -> List[str]:
        """生成重构建议"""
        suggestions = []

        # 统计各种结构
        if_count = 0
        for_count = 0
        try_count = 0
        nested_depth = 0

        for child in ast.walk(node):
            if isinstance(child, ast.If):
                if_count += 1
            elif isinstance(child, ast.For):
                for_count += 1
            elif isinstance(child, ast.Try):
                try_count += 1

        # 建议 1: 提取验证逻辑
        if if_count > 5:
            suggestions.append(
                f"提取验证逻辑: 发现 {if_count} 个 if 语句，可以提取为 Validator 类"
            )

        # 建议 2: 提取循环逻辑
        if for_count > 2:
            suggestions.append(
                f"提取循环逻辑: 发现 {for_count} 个 for 循环，可以提取为独立方法"
            )

        # 建议 3: 策略模式
        if if_count > 8:
            suggestions.append(
                "使用策略模式: 大量 if-elif-else 分支可以用策略模式替代"
            )

        # 建议 4: 拆分为多个方法
        if complexity > 30:
            suggestions.append(
                f"严重过高 (复杂度 {complexity}): 必须拆分为多个小方法，目标每个 < 15"
            )
        elif complexity > 20:
            suggestions.append(
                f"复杂度过高 ({complexity}): 建议拆分为 2-3 个方法"
            )

        return suggestions


def generate_refactoring_template(issue: ComplexityIssue) -> str:
    """生成重构模板代码"""
    template = f'''"""
重构: {issue.function_name}

原复杂度: {issue.complexity}
目标复杂度: < 15

重构建议:
'''

    for i, suggestion in enumerate(issue.suggestions, 1):
        template += f"{i}. {suggestion}\n"

    template += '''
"""

class {ClassName}:
    """重构后的处理器类"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def validate(self) -> Optional[str]:
        """验证输入

        Returns:
            错误消息，成功时返回 None
        """
        # TODO: 实现验证逻辑
        pass

    def process(self) -> Dict[str, Any]:
        """处理主逻辑"""
        # TODO: 实现处理逻辑
        pass


def {function_name}_refactored(data: Dict[str, Any]):
    """重构版本 - 复杂度 < 15

    原函数复杂度: {complexity}
    """
    processor = {ClassName}(data)

    # 验证
    error = processor.validate()
    if error:
        return error_response({{'error': error}}, 400)

    # 处理
    try:
        result = processor.process()
        return result
    except Exception as e:
        return error_response({{'error': str(e)}}, 500)
'''

    class_name = ''.join(word.capitalize() for word in issue.function_name.split('_')) + 'Processor'

    return template.format(
        ClassName=class_name,
        function_name=issue.function_name,
        complexity=issue.complexity
    )


def scan_and_report(base_dir: Path, output_file: Path) -> None:
    """扫描代码库并生成重构报告"""
    analyzer = ComplexityAnalyzer()
    issues = []

    # 扫描所有 Python 文件
    for py_file in base_dir.rglob('*.py'):
        if '__pycache__' in str(py_file) or 'venv' in str(py_file):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    issue = analyzer.analyze_function(node, py_file.relative_to(base_dir))
                    if issue:
                        issues.append(issue)

        except Exception:
            continue

    # 按复杂度排序
    issues.sort(key=lambda x: x.complexity, reverse=True)

    # 生成报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 高复杂度函数重构指南\n\n")
        f.write(f"**扫描时间**: 2026-09-06\n")
        f.write(f"**发现问题**: {len(issues)} 个函数复杂度 > 15\n\n")

        # 统计
        p0 = len([i for i in issues if i.complexity > 30])
        p1 = len([i for i in issues if 20 < i.complexity <= 30])
        p2 = len([i for i in issues if 15 < i.complexity <= 20])

        f.write("## 优先级分布\n\n")
        f.write(f"- 🔴 P0 (>30): {p0} 个\n")
        f.write(f"- 🟡 P1 (20-30): {p1} 个\n")
        f.write(f"- 🟢 P2 (15-20): {p2} 个\n\n")

        # Top 20
        f.write("## Top 20 最高复杂度函数\n\n")
        f.write("| 函数 | 复杂度 | 文件 | 行 |\n")
        f.write("|------|--------|------|----|\n")

        for issue in issues[:20]:
            f.write(f"| `{issue.function_name}` | {issue.complexity} | `{issue.file}` | {issue.line} |\n")

        f.write("\n")

        # 详细建议
        f.write("## 重构建议详情\n\n")

        for i, issue in enumerate(issues[:10], 1):
            f.write(f"### {i}. {issue.function_name} (复杂度 {issue.complexity})\n\n")
            f.write(f"**文件**: `{issue.file}:{issue.line}`\n\n")
            f.write("**建议**:\n\n")

            for j, suggestion in enumerate(issue.suggestions, 1):
                f.write(f"{j}. {suggestion}\n")

            f.write("\n**重构模板**:\n\n")
            f.write("```python\n")
            f.write(generate_refactoring_template(issue))
            f.write("\n```\n\n")
            f.write("---\n\n")

    print(f"✅ 报告已生成: {output_file}")
    print(f"   发现 {len(issues)} 个高复杂度函数")
    print(f"   P0 (>30): {p0} 个")
    print(f"   P1 (20-30): {p1} 个")
    print(f"   P2 (15-20): {p2} 个")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="批量复杂度分析和重构建议")
    parser.add_argument("--base-dir", type=str, default=".", help="基础目录")
    parser.add_argument("--output", type=str, default="COMPLEXITY_REFACTORING_GUIDE.md", help="输出文件")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    output_file = Path(args.output)

    print(f"🔍 扫描目录: {base_dir}")
    print(f"📝 分析复杂度...\n")

    scan_and_report(base_dir, output_file)


if __name__ == "__main__":
    main()
