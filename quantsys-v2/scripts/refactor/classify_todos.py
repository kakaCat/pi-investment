#!/usr/bin/env python3
"""扫描并分类 TODO/FIXME 注释

Usage:
    python scripts/refactor/classify_todos.py > docs/refactor/todo-inventory.md
    python scripts/refactor/classify_todos.py --format json > todos.json
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import json

@dataclass
class TodoItem:
    """TODO 项"""
    file: str
    line: int
    type: str  # TODO or FIXME
    priority: str  # P0/P1/P2/P3
    category: str
    text: str
    context: str  # 代码上下文

# 优先级分类规则
PRIORITY_RULES = [
    # P0 - 安全/核心功能
    (r'auth|security|password|token|验证|认证', 'P0', '安全/认证'),
    (r'sql injection|xss|csrf', 'P0', '安全漏洞'),
    (r'error handling|exception|错误处理', 'P0', '错误处理'),
    
    # P1 - 重要功能
    (r'implement|实现.*逻辑|接入.*Service', 'P1', '功能未完成'),
    (r'database|query|数据库', 'P1', '数据库操作'),
    (r'api|endpoint|接口', 'P1', 'API 开发'),
    (r'backtest|strategy|回测|策略', 'P1', '量化逻辑'),
    
    # P2 - 优化改进
    (r'optimize|performance|性能|优化', 'P2', '性能优化'),
    (r'refactor|重构|cleanup|清理', 'P2', '代码重构'),
    (r'test|测试', 'P2', '测试'),
    
    # P3 - 低优先级
    (r'future|later|someday|将来|以后', 'P3', '长期规划'),
    (r'nice to have|optional|可选', 'P3', '可选功能'),
]

def classify_todo(text: str, file_path: str) -> Tuple[str, str]:
    """根据文本内容分类 TODO
    
    Returns:
        (priority, category)
    """
    text_lower = text.lower()
    
    # 检查是否在测试文件中 (降低优先级)
    is_test = 'test_' in file_path or '/tests/' in file_path
    
    for pattern, priority, category in PRIORITY_RULES:
        if re.search(pattern, text_lower):
            if is_test and priority == 'P0':
                priority = 'P1'  # 测试文件中的 P0 降为 P1
            return priority, category
    
    # 默认 P2
    return 'P2', '其他'

def scan_todos(root_dir: Path) -> List[TodoItem]:
    """扫描所有 Python 文件中的 TODO/FIXME"""
    todos = []
    
    # 排除目录
    exclude_dirs = {'venv', '__pycache__', '.git', 'node_modules', '.pytest_cache'}
    
    for py_file in root_dir.rglob('*.py'):
        # 跳过排除目录
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Cannot read {py_file}: {e}", file=sys.stderr)
            continue
        
        for i, line in enumerate(lines, start=1):
            # 匹配 TODO 或 FIXME
            match = re.search(r'#\s*(TODO|FIXME):?\s*(.+)', line, re.IGNORECASE)
            if match:
                todo_type = match.group(1).upper()
                text = match.group(2).strip()
                
                # 获取上下文 (前一行代码)
                context = ''
                if i > 1:
                    prev_line = lines[i-2].strip()
                    if prev_line and not prev_line.startswith('#'):
                        context = prev_line
                
                # 分类
                priority, category = classify_todo(text, str(py_file))
                
                todos.append(TodoItem(
                    file=str(py_file.relative_to(root_dir)),
                    line=i,
                    type=todo_type,
                    priority=priority,
                    category=category,
                    text=text,
                    context=context
                ))
    
    return todos

def format_markdown(todos: List[TodoItem]) -> str:
    """格式化为 Markdown 报告"""
    from collections import defaultdict
    
    # 按优先级分组
    by_priority = defaultdict(list)
    for todo in todos:
        by_priority[todo.priority].append(todo)
    
    # 生成报告
    output = ["# TODO/FIXME 清单", ""]
    output.append(f"**生成时间**: {Path.cwd()}")
    output.append(f"**总数**: {len(todos)}")
    output.append("")
    
    # 统计
    output.append("## 统计概览")
    output.append("")
    output.append("| 优先级 | 数量 | 说明 |")
    output.append("|--------|------|------|")
    output.append(f"| P0 | {len(by_priority['P0'])} | 紧急 - 安全/核心功能 |")
    output.append(f"| P1 | {len(by_priority['P1'])} | 重要 - 影响用户体验 |")
    output.append(f"| P2 | {len(by_priority['P2'])} | 一般 - 优化改进 |")
    output.append(f"| P3 | {len(by_priority['P3'])} | 低优先级 - 长期规划 |")
    output.append("")
    
    # 按类别统计
    from collections import Counter
    category_counts = Counter(todo.category for todo in todos)
    
    output.append("## 按类别统计")
    output.append("")
    output.append("| 类别 | 数量 |")
    output.append("|------|------|")
    for category, count in category_counts.most_common():
        output.append(f"| {category} | {count} |")
    output.append("")
    
    # 详细列表
    for priority in ['P0', 'P1', 'P2', 'P3']:
        items = by_priority[priority]
        if not items:
            continue
        
        output.append(f"## {priority} 优先级 ({len(items)} 项)")
        output.append("")
        
        # 按类别分组
        by_category = defaultdict(list)
        for item in items:
            by_category[item.category].append(item)
        
        for category, category_items in sorted(by_category.items()):
            output.append(f"### {category} ({len(category_items)})")
            output.append("")
            
            for item in category_items[:20]:  # 每类最多显示 20 个
                output.append(f"- **{item.file}:{item.line}** - {item.text}")
                if item.context:
                    output.append(f"  ```python")
                    output.append(f"  {item.context}")
                    output.append(f"  ```")
            
            if len(category_items) > 20:
                output.append(f"  ... 还有 {len(category_items) - 20} 项")
            
            output.append("")
    
    return "\n".join(output)

def format_json(todos: List[TodoItem]) -> str:
    """格式化为 JSON"""
    return json.dumps(
        [asdict(todo) for todo in todos],
        indent=2,
        ensure_ascii=False
    )

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='扫描并分类 TODO/FIXME 注释')
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown',
                        help='输出格式')
    parser.add_argument('--root', type=Path, default=Path('.'),
                        help='项目根目录')
    
    args = parser.parse_args()
    
    print(f"Scanning {args.root}...", file=sys.stderr)
    todos = scan_todos(args.root)
    print(f"Found {len(todos)} TODO/FIXME items", file=sys.stderr)
    
    if args.format == 'markdown':
        print(format_markdown(todos))
    else:
        print(format_json(todos))

if __name__ == '__main__':
    main()
