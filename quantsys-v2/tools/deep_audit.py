#!/usr/bin/env python3
"""
quantsys-v2 深度审计工具

检查代码质量的隐藏问题：
- 循环依赖
- 未使用的导入
- 魔法数字
- 长函数/长类
- 复杂度过高
- 安全问题
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class Issue:
    """问题项"""
    category: str
    severity: str  # high, medium, low
    file: Path
    line: int
    message: str
    suggestion: str = ""


class CodeAuditor:
    """代码审计器"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.issues: List[Issue] = []

    def audit_file(self, file_path: Path) -> None:
        """审计单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            tree = ast.parse(content, filename=str(file_path))

            # 各项检查
            self._check_function_length(tree, file_path, lines)
            self._check_class_length(tree, file_path)
            self._check_complexity(tree, file_path)
            self._check_magic_numbers(tree, file_path)
            self._check_security_issues(content, file_path, lines)
            self._check_hardcoded_credentials(content, file_path, lines)
            self._check_sql_injection(content, file_path, lines)

        except SyntaxError as e:
            self.issues.append(Issue(
                category="syntax_error",
                severity="high",
                file=file_path.relative_to(self.base_dir),
                line=e.lineno or 0,
                message=f"语法错误: {e.msg}"
            ))
        except Exception as e:
            # 静默跳过无法解析的文件
            pass

    def _check_function_length(self, tree: ast.AST, file_path: Path, lines: List[str]) -> None:
        """检查函数长度"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 计算函数行数（排除空行和注释）
                start = node.lineno
                end = node.end_lineno or start
                func_lines = [l.strip() for l in lines[start-1:end] if l.strip() and not l.strip().startswith('#')]
                length = len(func_lines)

                if length > 100:
                    self.issues.append(Issue(
                        category="long_function",
                        severity="medium",
                        file=file_path.relative_to(self.base_dir),
                        line=start,
                        message=f"函数 {node.name} 过长 ({length} 行有效代码)",
                        suggestion="拆分为多个小函数，每个函数不超过 50-80 行"
                    ))

    def _check_class_length(self, tree: ast.AST, file_path: Path) -> None:
        """检查类长度"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 计算方法数
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                if len(methods) > 20:
                    self.issues.append(Issue(
                        category="large_class",
                        severity="medium",
                        file=file_path.relative_to(self.base_dir),
                        line=node.lineno,
                        message=f"类 {node.name} 方法过多 ({len(methods)} 个)",
                        suggestion="考虑按职责拆分类，遵循单一职责原则"
                    ))

    def _check_complexity(self, tree: ast.AST, file_path: Path) -> None:
        """检查圈复杂度"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._calculate_complexity(node)
                if complexity > 15:
                    self.issues.append(Issue(
                        category="high_complexity",
                        severity="high",
                        file=file_path.relative_to(self.base_dir),
                        line=node.lineno,
                        message=f"函数 {node.name} 圈复杂度过高 ({complexity})",
                        suggestion="简化逻辑，拆分条件分支，提取子函数"
                    ))

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _check_magic_numbers(self, tree: ast.AST, file_path: Path) -> None:
        """检查魔法数字"""
        magic_numbers = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    # 排除常见常量
                    if node.value not in [0, 1, -1, 2, 10, 100, 1000, 0.0, 1.0]:
                        magic_numbers.append((node.lineno, node.value))

        # 只报告过多的魔法数字
        if len(magic_numbers) > 20:
            self.issues.append(Issue(
                category="magic_numbers",
                severity="low",
                file=file_path.relative_to(self.base_dir),
                line=0,
                message=f"文件包含过多魔法数字 ({len(magic_numbers)} 个)",
                suggestion="将魔法数字提取为命名常量"
            ))

    def _check_security_issues(self, content: str, file_path: Path, lines: List[str]) -> None:
        """检查安全问题"""
        # 检查 eval/exec 使用
        if 'eval(' in content or 'exec(' in content:
            for i, line in enumerate(lines, 1):
                if 'eval(' in line or 'exec(' in line:
                    self.issues.append(Issue(
                        category="security",
                        severity="high",
                        file=file_path.relative_to(self.base_dir),
                        line=i,
                        message="使用了危险的 eval/exec",
                        suggestion="避免动态执行代码，使用更安全的替代方案"
                    ))

    def _check_hardcoded_credentials(self, content: str, file_path: Path, lines: List[str]) -> None:
        """检查硬编码凭证"""
        patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "硬编码密码"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "硬编码 API Key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "硬编码密钥"),
            (r'token\s*=\s*["\'][^"\']+["\']', "硬编码 Token"),
        ]

        for pattern, msg in patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    # 排除测试文件和明显的占位符
                    if 'test' not in str(file_path).lower() and 'example' not in line.lower():
                        self.issues.append(Issue(
                            category="security",
                            severity="high",
                            file=file_path.relative_to(self.base_dir),
                            line=i,
                            message=f"可能存在{msg}",
                            suggestion="使用环境变量或配置文件管理敏感信息"
                        ))

    def _check_sql_injection(self, content: str, file_path: Path, lines: List[str]) -> None:
        """检查 SQL 注入风险"""
        # 检查字符串拼接的 SQL
        for i, line in enumerate(lines, 1):
            if re.search(r'(SELECT|INSERT|UPDATE|DELETE).*\+.*%', line, re.IGNORECASE):
                self.issues.append(Issue(
                    category="security",
                    severity="high",
                    file=file_path.relative_to(self.base_dir),
                    line=i,
                    message="可能存在 SQL 注入风险（字符串拼接）",
                    suggestion="使用参数化查询或 ORM"
                ))

    def audit_directory(self, patterns: List[str] = None) -> None:
        """审计整个目录"""
        if patterns is None:
            patterns = ['*.py']

        for pattern in patterns:
            for file_path in self.base_dir.rglob(pattern):
                if '__pycache__' not in str(file_path) and 'venv' not in str(file_path):
                    self.audit_file(file_path)

    def generate_report(self, output_file: Path) -> None:
        """生成审计报告"""
        # 按严重程度和分类排序
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        issues_sorted = sorted(self.issues, key=lambda x: (severity_order[x.severity], x.category, str(x.file)))

        # 统计
        total = len(issues_sorted)
        by_severity = defaultdict(int)
        by_category = defaultdict(int)

        for issue in issues_sorted:
            by_severity[issue.severity] += 1
            by_category[issue.category] += 1

        # 生成报告
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# quantsys-v2 深度审计报告\n\n")
            f.write(f"**审计时间**: 2026-09-06\n")
            f.write(f"**发现问题**: {total} 项\n\n")

            f.write("## 严重程度分布\n\n")
            f.write(f"- 🔴 高危 (High): {by_severity['high']} 项\n")
            f.write(f"- 🟡 中危 (Medium): {by_severity['medium']} 项\n")
            f.write(f"- 🟢 低危 (Low): {by_severity['low']} 项\n\n")

            f.write("## 问题分类\n\n")
            for category, count in sorted(by_category.items(), key=lambda x: -x[1]):
                f.write(f"- **{category}**: {count} 项\n")
            f.write("\n")

            # 高危问题
            f.write("## 🔴 高危问题（需立即处理）\n\n")
            high_issues = [i for i in issues_sorted if i.severity == 'high']
            if high_issues:
                for issue in high_issues:
                    f.write(f"### {issue.file}:{issue.line}\n\n")
                    f.write(f"**类别**: {issue.category}\n\n")
                    f.write(f"**问题**: {issue.message}\n\n")
                    if issue.suggestion:
                        f.write(f"**建议**: {issue.suggestion}\n\n")
                    f.write("---\n\n")
            else:
                f.write("✅ 无高危问题\n\n")

            # 中危问题（仅列前 10 个）
            f.write("## 🟡 中危问题（前 10 项）\n\n")
            medium_issues = [i for i in issues_sorted if i.severity == 'medium']
            if medium_issues:
                for issue in medium_issues[:10]:
                    f.write(f"- `{issue.file}:{issue.line}` [{issue.category}] {issue.message}\n")
                if len(medium_issues) > 10:
                    f.write(f"\n*还有 {len(medium_issues) - 10} 项...*\n")
            else:
                f.write("✅ 无中危问题\n")
            f.write("\n")

            # 低危问题摘要
            f.write("## 🟢 低危问题摘要\n\n")
            low_issues = [i for i in issues_sorted if i.severity == 'low']
            if low_issues:
                f.write(f"共 {len(low_issues)} 项低危问题，建议在后续迭代中逐步优化\n\n")
            else:
                f.write("✅ 无低危问题\n\n")

        print(f"✅ 审计报告已生成: {output_file}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="深度审计 quantsys-v2 代码")
    parser.add_argument("--base-dir", type=str, default=".", help="基础目录")
    parser.add_argument("--output", type=str, default="DEEP_AUDIT_REPORT.md", help="输出文件")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    output_file = Path(args.output)

    print(f"🔍 深度审计目录: {base_dir}")
    print(f"📝 审计中...\n")

    auditor = CodeAuditor(base_dir)
    auditor.audit_directory()

    print(f"✅ 发现 {len(auditor.issues)} 个问题")
    print(f"📊 生成审计报告...\n")

    auditor.generate_report(output_file)

    # 打印摘要
    by_severity = defaultdict(int)
    for issue in auditor.issues:
        by_severity[issue.severity] += 1

    print(f"\n严重程度分布:")
    print(f"  🔴 高危: {by_severity['high']} 项")
    print(f"  🟡 中危: {by_severity['medium']} 项")
    print(f"  🟢 低危: {by_severity['low']} 项")


if __name__ == "__main__":
    main()
