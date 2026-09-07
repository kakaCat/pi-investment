#!/usr/bin/env python3
"""
线程使用检测工具

扫描项目中所有线程使用，分析潜在问题：
- threading.Thread 直接创建
- ThreadPoolExecutor 使用
- 线程泄漏风险
- 缺乏生命周期管理
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ThreadUsage:
    """线程使用记录"""
    file_path: str
    line_number: int
    usage_type: str  # 'Thread', 'ThreadPoolExecutor', 'start_new_thread', etc.
    code_snippet: str
    context: str = ""  # 上下文信息（类名、函数名等）
    has_daemon: bool = False
    has_join: bool = False
    has_name: bool = False


@dataclass
class ThreadAnalysisResult:
    """线程使用分析结果"""
    total_files: int = 0
    thread_usages: List[ThreadUsage] = field(default_factory=list)

    # 按类型分组
    by_type: Dict[str, List[ThreadUsage]] = field(default_factory=lambda: defaultdict(list))

    # 按文件分组
    by_file: Dict[str, List[ThreadUsage]] = field(default_factory=lambda: defaultdict(list))

    # 风险标记
    risky_usages: List[ThreadUsage] = field(default_factory=list)


class ThreadUsageDetector(ast.NodeVisitor):
    """AST访问器：检测线程使用"""

    def __init__(self, file_path: str, source_lines: List[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.usages: List[ThreadUsage] = []
        self.current_context: List[str] = []

        # 检测的模式
        self.thread_patterns = {
            'threading.Thread',
            'Thread',
            'threading.start_new_thread',
            '_thread.start_new_thread',
        }

        self.executor_patterns = {
            'ThreadPoolExecutor',
            'concurrent.futures.ThreadPoolExecutor',
        }

    def visit_ClassDef(self, node: ast.ClassDef):
        """访问类定义"""
        self.current_context.append(f"class {node.name}")
        self.generic_visit(node)
        self.current_context.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """访问函数定义"""
        self.current_context.append(f"def {node.name}")
        self.generic_visit(node)
        self.current_context.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """访问异步函数定义"""
        self.current_context.append(f"async def {node.name}")
        self.generic_visit(node)
        self.current_context.pop()

    def visit_Call(self, node: ast.Call):
        """访问函数调用"""
        # 检测 Thread 创建
        if isinstance(node.func, ast.Name):
            if node.func.id in {'Thread', 'ThreadPoolExecutor'}:
                self._record_usage(node, node.func.id)

        # 检测 threading.Thread()
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in {'Thread', 'start_new_thread', 'ThreadPoolExecutor'}:
                usage_type = self._get_full_name(node.func)
                self._record_usage(node, usage_type)

        self.generic_visit(node)

    def _get_full_name(self, node: ast.Attribute) -> str:
        """获取完整名称（如 threading.Thread）"""
        parts = []
        current = node

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return '.'.join(reversed(parts))

    def _record_usage(self, node: ast.Call, usage_type: str):
        """记录线程使用"""
        line_number = node.lineno

        # 提取代码片段（可能跨多行）
        end_line = getattr(node, 'end_lineno', line_number)
        code_lines = self.source_lines[line_number - 1:end_line]
        code_snippet = ''.join(code_lines).strip()

        # 检测关键字参数
        has_daemon = any(
            kw.arg == 'daemon' for kw in node.keywords
        )
        has_name = any(
            kw.arg in {'name', 'thread_name_prefix'} for kw in node.keywords
        )

        # 检测是否有 .join() 调用（简单启发式）
        context_start = max(0, line_number - 5)
        context_end = min(len(self.source_lines), line_number + 10)
        context_code = '\n'.join(self.source_lines[context_start:context_end])
        has_join = '.join()' in context_code

        usage = ThreadUsage(
            file_path=self.file_path,
            line_number=line_number,
            usage_type=usage_type,
            code_snippet=code_snippet,
            context=' > '.join(self.current_context) if self.current_context else '<module>',
            has_daemon=has_daemon,
            has_join=has_join,
            has_name=has_name,
        )

        self.usages.append(usage)


def scan_file(file_path: Path) -> List[ThreadUsage]:
    """扫描单个文件"""
    try:
        source = file_path.read_text(encoding='utf-8')
        source_lines = source.splitlines(keepends=True)

        # 快速预检：文件中是否包含线程相关关键字
        if not any(keyword in source for keyword in [
            'Thread', 'ThreadPool', 'start_new_thread', '_thread'
        ]):
            return []

        tree = ast.parse(source, filename=str(file_path))
        detector = ThreadUsageDetector(str(file_path), source_lines)
        detector.visit(tree)

        return detector.usages

    except SyntaxError:
        # 忽略语法错误的文件
        return []
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
        return []


def scan_project(root_dir: Path) -> ThreadAnalysisResult:
    """扫描整个项目"""
    result = ThreadAnalysisResult()

    # 扫描所有 Python 文件
    for py_file in root_dir.rglob('*.py'):
        # 排除虚拟环境和缓存
        if any(part in py_file.parts for part in ['.venv', 'venv', '__pycache__', '.git']):
            continue

        result.total_files += 1
        usages = scan_file(py_file)

        for usage in usages:
            result.thread_usages.append(usage)
            result.by_type[usage.usage_type].append(usage)
            result.by_file[usage.file_path].append(usage)

            # 标记风险使用
            if not usage.has_name or (not usage.has_daemon and not usage.has_join):
                result.risky_usages.append(usage)

    return result


def print_report(result: ThreadAnalysisResult, verbose: bool = False):
    """打印分析报告"""
    print("=" * 80)
    print("线程使用检测报告")
    print("=" * 80)
    print()

    print(f"📊 扫描统计:")
    print(f"  - 扫描文件数: {result.total_files}")
    print(f"  - 线程使用总数: {len(result.thread_usages)}")
    print(f"  - 涉及文件数: {len(result.by_file)}")
    print(f"  - 风险使用数: {len(result.risky_usages)} ⚠️")
    print()

    # 按类型统计
    print("📈 按类型分布:")
    for usage_type, usages in sorted(result.by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  - {usage_type}: {len(usages)} 处")
    print()

    # 风险分析
    print("⚠️  风险使用 (缺少 name 或生命周期管理):")
    print()

    if not result.risky_usages:
        print("  ✅ 未发现明显风险使用")
    else:
        # 按文件分组显示
        risky_by_file = defaultdict(list)
        for usage in result.risky_usages:
            risky_by_file[usage.file_path].append(usage)

        for file_path in sorted(risky_by_file.keys()):
            usages = risky_by_file[file_path]
            print(f"  📄 {file_path}")
            print(f"     风险数: {len(usages)}")

            if verbose:
                for usage in usages:
                    issues = []
                    if not usage.has_name:
                        issues.append("缺少name")
                    if not usage.has_daemon:
                        issues.append("未设置daemon")
                    if not usage.has_join:
                        issues.append("未调用join()")

                    print(f"     Line {usage.line_number}: {usage.usage_type}")
                    print(f"       上下文: {usage.context}")
                    print(f"       问题: {', '.join(issues)}")
                    print(f"       代码: {usage.code_snippet[:80]}...")
                    print()
            print()

    # 文件热点
    print("🔥 线程使用热点文件 (前10):")
    top_files = sorted(result.by_file.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    for file_path, usages in top_files:
        print(f"  {len(usages):2d} 处 - {file_path}")
    print()

    # 推荐方案
    print("=" * 80)
    print("💡 推荐统一方案")
    print("=" * 80)
    print()
    print("1️⃣  创建 infrastructure/threading/thread_pool.py:")
    print("""
    from concurrent.futures import ThreadPoolExecutor
    from typing import Optional

    class ManagedThreadPool:
        \"\"\"统一的线程池管理器\"\"\"

        def __init__(self, max_workers: int = 10, thread_name_prefix: str = "worker"):
            self.executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=thread_name_prefix
            )

        def submit(self, fn, *args, **kwargs):
            return self.executor.submit(fn, *args, **kwargs)

        def shutdown(self, wait: bool = True):
            self.executor.shutdown(wait=wait)

    # 全局池实例
    default_pool = ManagedThreadPool(max_workers=10, thread_name_prefix="quantsys-worker")
    """)
    print()

    print("2️⃣  使用示例:")
    print("""
    # BEFORE: 直接创建 Thread
    thread = threading.Thread(target=worker_func, args=(data,))
    thread.start()

    # AFTER: 使用统一线程池
    from infrastructure.threading.thread_pool import default_pool
    future = default_pool.submit(worker_func, data)
    result = future.result()  # 等待结果
    """)
    print()

    print("3️⃣  监控接口:")
    print("""
    def get_thread_pool_status() -> dict:
        \"\"\"获取线程池状态\"\"\"
        executor = default_pool.executor
        return {
            "max_workers": executor._max_workers,
            "active_threads": len(executor._threads),
            "pending_tasks": executor._work_queue.qsize(),
        }
    """)
    print()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='检测项目中的线程使用')
    parser.add_argument('--root', type=str, default='.',
                        help='项目根目录 (默认: 当前目录)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细信息')
    parser.add_argument('--file', type=str,
                        help='只检查指定文件')

    args = parser.parse_args()

    if args.file:
        # 单文件模式
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)

        usages = scan_file(file_path)
        print(f"文件 {args.file} 中发现 {len(usages)} 处线程使用:\n")
        for usage in usages:
            print(f"Line {usage.line_number}: {usage.usage_type}")
            print(f"  上下文: {usage.context}")
            print(f"  代码: {usage.code_snippet}")
            print(f"  has_name={usage.has_name}, has_daemon={usage.has_daemon}, has_join={usage.has_join}")
            print()
    else:
        # 项目扫描模式
        root_dir = Path(args.root).resolve()
        if not root_dir.exists():
            print(f"Error: Directory not found: {args.root}", file=sys.stderr)
            sys.exit(1)

        result = scan_project(root_dir)
        print_report(result, verbose=args.verbose)


if __name__ == '__main__':
    main()
