#!/usr/bin/env python3
"""
TODO/FIXME 分类和清理工具

分析代码中的 TODO/FIXME，按优先级分类并生成清理计划
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class TODOCategory(Enum):
    """TODO 分类"""
    IMMEDIATE = "立即修复"  # 功能不完整，影响使用
    ENHANCEMENT = "功能增强"  # 优化改进
    TECHNICAL_DEBT = "技术债务"  # 代码改进
    DOCUMENTATION = "文档完善"  # 注释说明
    DEPRECATED = "已废弃"  # 过期内容


@dataclass
class TODOItem:
    """TODO 项"""
    file: Path
    line: int
    category: TODOCategory
    content: str
    priority: int  # 1=高, 2=中, 3=低


def classify_todo(content: str) -> Tuple[TODOCategory, int]:
    """分类 TODO 项

    Args:
        content: TODO 内容

    Returns:
        (分类, 优先级)
    """
    content_lower = content.lower()

    # 立即修复 - 功能不完整
    if any(kw in content_lower for kw in ['实现', 'implement', '修复', 'fix', 'broken', '缺失']):
        if any(kw in content_lower for kw in ['暂时', '临时', 'temporary', 'workaround']):
            return TODOCategory.IMMEDIATE, 1
        return TODOCategory.IMMEDIATE, 2

    # 已废弃
    if any(kw in content_lower for kw in ['废弃', 'deprecated', '已删除', 'removed']):
        return TODOCategory.DEPRECATED, 3

    # 文档完善
    if any(kw in content_lower for kw in ['文档', 'document', '说明', '注释']):
        return TODOCategory.DOCUMENTATION, 3

    # 功能增强
    if any(kw in content_lower for kw in ['优化', 'optimize', '改进', 'improve', '增强', 'enhance']):
        return TODOCategory.ENHANCEMENT, 2

    # 技术债务（默认）
    return TODOCategory.TECHNICAL_DEBT, 2


def scan_todos(base_dir: Path, patterns: List[str] = None) -> List[TODOItem]:
    """扫描 TODO/FIXME

    Args:
        base_dir: 基础目录
        patterns: 文件模式列表（默认 ['*.py']）

    Returns:
        TODO 项列表
    """
    if patterns is None:
        patterns = ['*.py']

    todos = []

    for pattern in patterns:
        for file_path in base_dir.rglob(pattern):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, start=1):
                    # 匹配 TODO/FIXME
                    match = re.search(r'#\s*(TODO|FIXME):?\s*(.+)', line, re.IGNORECASE)
                    if match:
                        content = match.group(2).strip()
                        category, priority = classify_todo(content)

                        todos.append(TODOItem(
                            file=file_path.relative_to(base_dir),
                            line=line_num,
                            category=category,
                            content=content,
                            priority=priority
                        ))

            except Exception as e:
                print(f"⚠️  无法读取 {file_path}: {e}")

    return todos


# TODO: Refactor - complexity 17 (target < 15)

# TODO: 复杂度 17 - 需要重构拆分为更小的函数

def _validate_generate_report_input(*args, **kwargs):
    """验证输入参数"""
    pass

def _process_generate_report_data(data):
    """处理数据转换"""
    return data

def _build_generate_report_result(data):
    """构建返回结果"""
    return data

def _validate_generate_report_input(*args, **kwargs):
    """验证输入参数"""
    pass

def _process_generate_report_data(data):
    """处理数据转换"""
    return data

def _build_generate_report_result(data):
    """构建返回结果"""
    return data

def generate_report(todos: List[TODOItem], output_file: Path) -> None:
    """生成清理报告

    Args:
        todos: TODO 项列表
        output_file: 输出文件路径
    """
    # 按优先级和分类排序
    todos_sorted = sorted(todos, key=lambda x: (x.priority, x.category.value))

    # 统计
    total = len(todos)
    by_category = {}
    by_priority = {1: 0, 2: 0, 3: 0}

    for todo in todos:
        by_category[todo.category] = by_category.get(todo.category, 0) + 1
        by_priority[todo.priority] += 1

    # 生成 Markdown 报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# TODO/FIXME 清理计划\n\n")
        f.write(f"**生成时间**: {Path.cwd()}\n")
        f.write(f"**总数**: {total} 项\n\n")

        f.write("## 统计概览\n\n")
        f.write("### 按优先级\n\n")
        f.write(f"- 🔴 P1 (高优先级): {by_priority[1]} 项\n")
        f.write(f"- 🟡 P2 (中优先级): {by_priority[2]} 项\n")
        f.write(f"- 🟢 P3 (低优先级): {by_priority[3]} 项\n\n")

        f.write("### 按分类\n\n")
        for category in TODOCategory:
            count = by_category.get(category, 0)
            if count > 0:
                f.write(f"- **{category.value}**: {count} 项\n")
        f.write("\n")

        f.write("## 清理策略\n\n")
        f.write("### 立即处理 (P1)\n\n")
        f.write("这些 TODO 影响功能完整性，应该立即修复或删除：\n\n")

        p1_todos = [t for t in todos_sorted if t.priority == 1]
        if p1_todos:
            for todo in p1_todos:
                f.write(f"- [ ] `{todo.file}:{todo.line}` - {todo.content}\n")
        else:
            f.write("✅ 无 P1 TODO\n")
        f.write("\n")

        f.write("### 本周处理 (P2 中的立即修复和技术债务)\n\n")
        p2_immediate = [t for t in todos_sorted
                       if t.priority == 2 and t.category in [TODOCategory.IMMEDIATE, TODOCategory.TECHNICAL_DEBT]]
        if p2_immediate:
            for todo in p2_immediate[:10]:  # 前 10 项
                f.write(f"- [ ] `{todo.file}:{todo.line}` - {todo.content}\n")
            if len(p2_immediate) > 10:
                f.write(f"\n*还有 {len(p2_immediate) - 10} 项...*\n")
        else:
            f.write("✅ 无紧急 P2 TODO\n")
        f.write("\n")

        f.write("### 转为 GitHub Issue (P2 功能增强)\n\n")
        enhancements = [t for t in todos_sorted if t.category == TODOCategory.ENHANCEMENT]
        if enhancements:
            for todo in enhancements[:5]:
                f.write(f"- [ ] `{todo.file}:{todo.line}` - {todo.content}\n")
            if len(enhancements) > 5:
                f.write(f"\n*还有 {len(enhancements) - 5} 项...*\n")
        f.write("\n")

        f.write("### 直接删除 (已废弃)\n\n")
        deprecated = [t for t in todos_sorted if t.category == TODOCategory.DEPRECATED]
        if deprecated:
            for todo in deprecated:
                f.write(f"- [ ] `{todo.file}:{todo.line}` - {todo.content}\n")
        else:
            f.write("✅ 无废弃 TODO\n")
        f.write("\n")

        f.write("## 详细列表\n\n")
        current_file = None
        for todo in todos_sorted:
            if todo.file != current_file:
                current_file = todo.file
                f.write(f"\n### {todo.file}\n\n")

            priority_emoji = {1: "🔴", 2: "🟡", 3: "🟢"}[todo.priority]
            f.write(f"{priority_emoji} **L{todo.line}** [{todo.category.value}]: {todo.content}\n\n")

    print(f"✅ 报告已生成: {output_file}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="扫描和分类 TODO/FIXME")
    parser.add_argument("--base-dir", type=str, default=".", help="基础目录")
    parser.add_argument("--output", type=str, default="TODO_CLEANUP_PLAN.md", help="输出文件")
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    output_file = Path(args.output)

    print(f"🔍 扫描目录: {base_dir}")
    print(f"📝 扫描 Python 文件中的 TODO/FIXME...\n")

    todos = scan_todos(base_dir)

    print(f"✅ 发现 {len(todos)} 个 TODO/FIXME 项")
    print(f"📊 生成清理报告...\n")

    generate_report(todos, output_file)

    # 打印摘要
    by_priority = {1: 0, 2: 0, 3: 0}
    for todo in todos:
        by_priority[todo.priority] += 1

    print(f"\n优先级分布:")
    print(f"  🔴 P1: {by_priority[1]} 项")
    print(f"  🟡 P2: {by_priority[2]} 项")
    print(f"  🟢 P3: {by_priority[3]} 项")


if __name__ == "__main__":
    main()