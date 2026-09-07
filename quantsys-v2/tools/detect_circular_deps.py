#!/usr/bin/env python3
"""
循环依赖检测工具

扫描 quantsys-v2 项目，检测 Python 模块间的循环导入依赖。
循环依赖会导致：
- 难以理解的代码结构
- 测试困难
- 潜在的运行时导入错误
"""

import ast
import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import argparse


class ImportAnalyzer(ast.NodeVisitor):
    """分析 Python 文件中的 import 语句"""

    def __init__(self, module_path: str):
        self.module_path = module_path
        self.imports: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        """处理 import xxx 语句"""
        for alias in node.names:
            self.imports.add(alias.name.split('.')[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """处理 from xxx import yyy 语句"""
        if node.module:
            # from xxx import yyy
            self.imports.add(node.module.split('.')[0])
        elif node.level > 0:
            # from . import xxx 或 from .. import xxx (相对导入)
            # 需要根据当前模块路径计算实际导入的模块
            pass
        self.generic_visit(node)


def normalize_module_name(file_path: Path, project_root: Path) -> str:
    """将文件路径转换为模块名

    例如: quantsys-v2/application/services/market_data_service.py
    -> application.services.market_data_service
    """
    relative = file_path.relative_to(project_root)
    # 移除 .py 后缀
    if relative.suffix == '.py':
        relative = relative.with_suffix('')
    # 转换路径分隔符为点号
    parts = list(relative.parts)
    # 移除 __init__
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def build_dependency_graph(project_root: Path) -> Dict[str, Set[str]]:
    """构建项目的依赖图

    返回: {模块名: {依赖的模块名集合}}
    """
    graph = defaultdict(set)

    # 扫描所有 Python 文件
    for py_file in project_root.rglob("*.py"):
        # 跳过一些目录
        if any(skip in str(py_file) for skip in ['__pycache__', 'venv', '.git', 'tests']):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(py_file))
            analyzer = ImportAnalyzer(str(py_file))
            analyzer.visit(tree)

            module_name = normalize_module_name(py_file, project_root)

            # 只记录项目内部的依赖
            for imported in analyzer.imports:
                # 只保留顶级模块名（如 application, domain, infrastructure）
                if imported in ['application', 'domain', 'infrastructure', 'adapters', 'live_trading']:
                    graph[module_name].add(imported)

        except Exception as e:
            # 忽略语法错误的文件
            pass

    return graph


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """使用 DFS 查找图中的所有循环

    返回: 循环路径列表
    """
    cycles = []
    visited = set()
    rec_stack = set()
    path = []

    def dfs(node: str) -> bool:
        """DFS 遍历，返回是否发现循环"""
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                # 发现循环
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
                return True

        path.pop()
        rec_stack.remove(node)
        return False

    # 对每个未访问的节点进行 DFS
    for node in graph:
        if node not in visited:
            dfs(node)

    return cycles


def detect_direct_cycles(project_root: Path) -> List[Tuple[str, str, int]]:
    """检测直接的双向依赖（A imports B, B imports A）

    返回: [(模块A, 模块B, 循环数量)]
    """
    graph = defaultdict(set)

    # 构建详细的依赖图（保留完整模块路径）
    for py_file in project_root.rglob("*.py"):
        if any(skip in str(py_file) for skip in ['__pycache__', 'venv', '.git', 'tests', 'archived_scripts']):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(py_file))
            analyzer = ImportAnalyzer(str(py_file))
            analyzer.visit(tree)

            module_name = normalize_module_name(py_file, project_root)

            # 记录所有导入
            for imported in analyzer.imports:
                graph[module_name].add(imported)

        except:
            pass

    # 查找直接循环
    cycles = []
    checked = set()

    for module_a in graph:
        for module_b in graph[module_a]:
            if module_b in graph and module_a in graph[module_b]:
                # 发现双向依赖
                pair = tuple(sorted([module_a, module_b]))
                if pair not in checked:
                    checked.add(pair)
                    cycles.append((module_a, module_b, 1))

    return cycles


def analyze_layer_violations(project_root: Path) -> Dict[str, List[str]]:
    """分析分层架构违规

    检查依赖方向是否符合：
    adapters -> application -> domain
    infrastructure -> domain
    """
    violations = defaultdict(list)

    # 定义层次
    layers = {
        'domain': 0,           # 最内层，不应该依赖其他层
        'application': 1,      # 可以依赖 domain
        'infrastructure': 1,   # 可以依赖 domain
        'adapters': 2,         # 可以依赖 application, domain
    }

    for py_file in project_root.rglob("*.py"):
        if any(skip in str(py_file) for skip in ['__pycache__', 'venv', '.git', 'tests', 'archived_scripts']):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(py_file))
            analyzer = ImportAnalyzer(str(py_file))
            analyzer.visit(tree)

            module_name = normalize_module_name(py_file, project_root)

            # 确定当前模块所在层
            current_layer = None
            for layer in layers:
                if module_name.startswith(layer):
                    current_layer = layer
                    break

            if not current_layer:
                continue

            # 检查导入的模块
            for imported in analyzer.imports:
                imported_layer = None
                for layer in layers:
                    if imported.startswith(layer):
                        imported_layer = layer
                        break

                if not imported_layer:
                    continue

                # 检查依赖方向
                if current_layer == 'domain' and imported_layer in layers:
                    # domain 层不应该依赖任何其他层
                    violations[module_name].append(f"domain 层违规: 依赖 {imported}")

                elif current_layer == 'application' and imported_layer == 'adapters':
                    # application 不应该依赖 adapters
                    violations[module_name].append(f"application 层违规: 依赖 {imported}")

                elif current_layer == 'infrastructure' and imported_layer in ['application', 'adapters']:
                    # infrastructure 不应该依赖 application 或 adapters
                    violations[module_name].append(f"infrastructure 层违规: 依赖 {imported}")

        except:
            pass

    return violations


def main():
    parser = argparse.ArgumentParser(description='检测 Python 项目中的循环依赖')
    parser.add_argument('--project-root', default='.', help='项目根目录')
    parser.add_argument('--mode', choices=['cycles', 'layers', 'all'], default='all',
                       help='检测模式: cycles=循环依赖, layers=分层违规, all=全部')
    args = parser.parse_args()

    # 如果在 tools 目录下运行，project_root 是上一级目录
    if Path(__file__).parent.name == 'tools':
        project_root = Path(__file__).parent.parent
    else:
        project_root = Path(args.project_root).resolve()

    if not project_root.exists():
        print(f"❌ 项目目录不存在: {project_root}")
        return 1

    print("=" * 70)
    print("循环依赖检测工具")
    print("=" * 70)
    print(f"项目路径: {project_root}")
    print()

    if args.mode in ['cycles', 'all']:
        print("🔍 检测循环依赖...")
        cycles = detect_direct_cycles(project_root)

        if cycles:
            print(f"\n⚠️  发现 {len(cycles)} 个直接循环依赖:\n")
            for i, (module_a, module_b, count) in enumerate(cycles, 1):
                print(f"{i}. {module_a}")
                print(f"   ↕️  {module_b}")
                print()
        else:
            print("✅ 未发现直接循环依赖\n")

    if args.mode in ['layers', 'all']:
        print("🔍 检测分层架构违规...")
        violations = analyze_layer_violations(project_root)

        if violations:
            print(f"\n⚠️  发现 {len(violations)} 个模块有分层违规:\n")
            for module, issues in sorted(violations.items())[:20]:  # 只显示前20个
                print(f"📁 {module}")
                for issue in issues[:3]:  # 每个模块只显示前3个违规
                    print(f"   • {issue}")
                if len(issues) > 3:
                    print(f"   ... 还有 {len(issues) - 3} 个违规")
                print()

            if len(violations) > 20:
                print(f"... 还有 {len(violations) - 20} 个模块有违规")
        else:
            print("✅ 未发现分层架构违规\n")

    print("=" * 70)
    print("检测完成")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
