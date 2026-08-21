#!/usr/bin/env python3
"""
服务层职责审计工具

分析 application/services 层的服务职责：
1. 识别服务职责重叠
2. 检查服务粒度是否合理
3. 分析服务间依赖关系
4. 检测服务方法数量和复杂度
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class MethodInfo:
    """方法信息"""
    name: str
    line_count: int
    params: List[str]
    calls_services: List[str]  # 调用的其他服务
    docstring: str = ""


@dataclass
class ServiceInfo:
    """服务信息"""
    name: str
    file_path: Path
    methods: List[MethodInfo]
    dependencies: Set[str]  # 依赖的其他服务
    repository_deps: Set[str]  # 依赖的 Repository
    total_lines: int
    has_init: bool


class ServiceAnalyzer(ast.NodeVisitor):
    """服务分析器"""

    def __init__(self, file_path: Path, source_code: str):
        self.file_path = file_path
        self.source_lines = source_code.split('\n')
        self.services: List[ServiceInfo] = []
        self.current_service = None
        self.current_method = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """访问类定义"""
        # 只分析以 Service 结尾的类
        if node.name.endswith('Service'):
            service_info = ServiceInfo(
                name=node.name,
                file_path=self.file_path,
                methods=[],
                dependencies=set(),
                repository_deps=set(),
                total_lines=self._count_lines(node),
                has_init=False
            )
            self.current_service = service_info
            self.services.append(service_info)

            # 分析类的依赖（从 __init__ 参数）
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                    service_info.has_init = True
                    self._analyze_init_deps(item, service_info)

            self.generic_visit(node)
            self.current_service = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """访问函数定义"""
        if self.current_service and node.name != '__init__':
            # 提取方法信息
            params = [arg.arg for arg in node.args.args if arg.arg != 'self']
            docstring = ast.get_docstring(node) or ""

            method_info = MethodInfo(
                name=node.name,
                line_count=self._count_lines(node),
                params=params,
                calls_services=[],
                docstring=docstring
            )

            # 分析方法中调用的服务
            self.current_method = method_info
            self.generic_visit(node)
            self.current_method = None

            self.current_service.methods.append(method_info)

    def visit_Attribute(self, node: ast.Attribute):
        """访问属性访问"""
        if self.current_method and isinstance(node.value, ast.Name):
            # 检测 self.xxx_service 或 self.xxx_repository 调用
            if node.value.id == 'self':
                attr_name = node.attr
                if 'service' in attr_name.lower():
                    self.current_method.calls_services.append(attr_name)
                    self.current_service.dependencies.add(attr_name)
                elif 'repository' in attr_name.lower() or 'repo' in attr_name.lower():
                    self.current_service.repository_deps.add(attr_name)

        self.generic_visit(node)

    def _analyze_init_deps(self, init_node: ast.FunctionDef, service_info: ServiceInfo):
        """分析 __init__ 中的依赖注入"""
        for arg in init_node.args.args:
            if arg.arg == 'self':
                continue
            arg_name = arg.arg
            if 'service' in arg_name.lower():
                service_info.dependencies.add(arg_name)
            elif 'repository' in arg_name.lower() or 'repo' in arg_name.lower():
                service_info.repository_deps.add(arg_name)

    def _count_lines(self, node: ast.AST) -> int:
        """计算 AST 节点的代码行数"""
        if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
            return node.end_lineno - node.lineno + 1
        return 0


def analyze_services_directory(services_dir: Path) -> List[ServiceInfo]:
    """分析整个 services 目录"""
    all_services = []

    for py_file in services_dir.rglob("*.py"):
        if py_file.name.startswith('__'):
            continue

        try:
            source_code = py_file.read_text(encoding='utf-8')
            tree = ast.parse(source_code, filename=str(py_file))

            analyzer = ServiceAnalyzer(py_file, source_code)
            analyzer.visit(tree)

            all_services.extend(analyzer.services)

        except SyntaxError as e:
            print(f"⚠️  Syntax error in {py_file}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Error analyzing {py_file}: {e}", file=sys.stderr)

    return all_services


def detect_responsibility_overlap(services: List[ServiceInfo]) -> List[Tuple[str, str, List[str]]]:
    """检测服务职责重叠"""
    overlaps = []

    # 构建方法名到服务的映射
    method_to_services = defaultdict(list)
    for service in services:
        for method in service.methods:
            # 提取方法的关键词（去掉 get_, create_, update_ 等前缀）
            keywords = extract_method_keywords(method.name)
            for keyword in keywords:
                method_to_services[keyword].append((service.name, method.name))

    # 查找重叠
    for keyword, service_methods in method_to_services.items():
        if len(service_methods) > 1:
            services_involved = [sm[0] for sm in service_methods]
            methods_involved = [sm[1] for sm in service_methods]
            overlaps.append((keyword, ', '.join(set(services_involved)), methods_involved))

    return overlaps


def extract_method_keywords(method_name: str) -> Set[str]:
    """从方法名提取关键词"""
    # 移除常见前缀
    prefixes = ['get_', 'create_', 'update_', 'delete_', 'fetch_', 'load_',
                'save_', 'find_', 'list_', 'search_', 'calculate_', 'compute_',
                'analyze_', 'process_', 'validate_', 'check_']

    clean_name = method_name
    for prefix in prefixes:
        if method_name.startswith(prefix):
            clean_name = method_name[len(prefix):]
            break

    # 按下划线分割，提取关键词
    parts = clean_name.split('_')
    # 过滤掉太短的词
    keywords = {p for p in parts if len(p) > 3}

    return keywords


def analyze_service_granularity(services: List[ServiceInfo]) -> Dict[str, List[ServiceInfo]]:
    """分析服务粒度"""
    granularity = {
        'too_large': [],      # 方法过多，职责过重
        'too_small': [],      # 方法过少，可能过度拆分
        'appropriate': [],    # 粒度合适
        'god_service': []     # 上帝服务（依赖过多）
    }

    for service in services:
        method_count = len(service.methods)
        dep_count = len(service.dependencies)

        # 检测上帝服务
        if dep_count > 8:
            granularity['god_service'].append(service)
        # 检测职责过重
        elif method_count > 20:
            granularity['too_large'].append(service)
        # 检测过度拆分
        elif method_count < 3 and service.total_lines < 100:
            granularity['too_small'].append(service)
        else:
            granularity['appropriate'].append(service)

    return granularity


def analyze_method_complexity(services: List[ServiceInfo]) -> List[Tuple[str, str, int]]:
    """分析方法复杂度（按代码行数）"""
    complex_methods = []

    for service in services:
        for method in service.methods:
            if method.line_count > 50:  # 超过 50 行认为过于复杂
                complex_methods.append((service.name, method.name, method.line_count))

    # 按行数降序排序
    complex_methods.sort(key=lambda x: x[2], reverse=True)

    return complex_methods


def build_service_dependency_graph(services: List[ServiceInfo]) -> Dict[str, Set[str]]:
    """构建服务依赖图"""
    graph = {}

    for service in services:
        # 依赖的服务名（去掉可能的前缀 self.）
        deps = {dep.replace('self.', '') for dep in service.dependencies}
        graph[service.name] = deps

    return graph


def detect_circular_dependencies(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """检测服务间循环依赖"""
    def dfs(node: str, visited: Set[str], path: List[str]) -> List[str]:
        if node in path:
            # 找到循环
            cycle_start = path.index(node)
            return path[cycle_start:] + [node]

        if node in visited:
            return []

        visited.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            cycle = dfs(neighbor, visited, path[:])
            if cycle:
                return cycle

        return []

    cycles = []
    visited = set()

    for node in graph:
        if node not in visited:
            cycle = dfs(node, visited, [])
            if cycle and cycle not in cycles:
                cycles.append(cycle)

    return cycles


def generate_report(services: List[ServiceInfo], output_path: Path):
    """生成审计报告"""
    report = []

    report.append("=" * 80)
    report.append("服务层职责审计报告")
    report.append("=" * 80)
    report.append("")

    # 1. 统计数据
    report.append("## 1. 统计数据")
    report.append("")
    report.append(f"总服务数: {len(services)}")
    total_methods = sum(len(s.methods) for s in services)
    report.append(f"总方法数: {total_methods}")
    avg_methods = total_methods / len(services) if services else 0
    report.append(f"平均每服务方法数: {avg_methods:.1f}")
    report.append("")

    # 2. 职责重叠分析
    report.append("## 2. 职责重叠分析")
    report.append("")
    overlaps = detect_responsibility_overlap(services)
    if overlaps:
        report.append(f"发现 {len(overlaps)} 处潜在职责重叠:")
        report.append("")
        for keyword, services_str, methods in overlaps[:10]:  # 只显示前 10 个
            report.append(f"  关键词: {keyword}")
            report.append(f"  涉及服务: {services_str}")
            report.append(f"  涉及方法: {', '.join(methods[:3])}...")
            report.append("")
    else:
        report.append("✅ 未发现明显的职责重叠")
        report.append("")

    # 3. 服务粒度分析
    report.append("## 3. 服务粒度分析")
    report.append("")
    granularity = analyze_service_granularity(services)

    if granularity['god_service']:
        report.append(f"⚠️  上帝服务 (依赖 >8): {len(granularity['god_service'])} 个")
        for service in granularity['god_service'][:5]:
            report.append(f"  - {service.name}: {len(service.dependencies)} 个依赖, {len(service.methods)} 个方法")
        report.append("")

    if granularity['too_large']:
        report.append(f"⚠️  职责过重 (方法 >20): {len(granularity['too_large'])} 个")
        for service in granularity['too_large'][:5]:
            report.append(f"  - {service.name}: {len(service.methods)} 个方法, {service.total_lines} 行")
        report.append("")

    if granularity['too_small']:
        report.append(f"ℹ️  可能过度拆分 (方法 <3, <100行): {len(granularity['too_small'])} 个")
        for service in granularity['too_small'][:5]:
            report.append(f"  - {service.name}: {len(service.methods)} 个方法, {service.total_lines} 行")
        report.append("")

    report.append(f"✅ 粒度合适: {len(granularity['appropriate'])} 个")
    report.append("")

    # 4. 方法复杂度分析
    report.append("## 4. 方法复杂度分析")
    report.append("")
    complex_methods = analyze_method_complexity(services)
    if complex_methods:
        report.append(f"发现 {len(complex_methods)} 个复杂方法 (>50 行):")
        report.append("")
        for service, method, lines in complex_methods[:10]:
            report.append(f"  - {service}.{method}: {lines} 行")
        report.append("")
    else:
        report.append("✅ 未发现过于复杂的方法")
        report.append("")

    # 5. 服务依赖分析
    report.append("## 5. 服务依赖分析")
    report.append("")
    dep_graph = build_service_dependency_graph(services)

    # 找出高度耦合的服务
    high_coupling = [(s, len(deps)) for s, deps in dep_graph.items() if len(deps) > 5]
    high_coupling.sort(key=lambda x: x[1], reverse=True)

    if high_coupling:
        report.append(f"⚠️  高度耦合的服务 (依赖 >5): {len(high_coupling)} 个")
        for service, dep_count in high_coupling[:10]:
            report.append(f"  - {service}: {dep_count} 个依赖")
        report.append("")

    # 检测循环依赖
    cycles = detect_circular_dependencies(dep_graph)
    if cycles:
        report.append(f"🔴 发现 {len(cycles)} 个循环依赖:")
        for cycle in cycles:
            report.append(f"  - {' -> '.join(cycle)}")
        report.append("")
    else:
        report.append("✅ 未发现服务间循环依赖")
        report.append("")

    # 6. Repository 依赖统计
    report.append("## 6. Repository 依赖统计")
    report.append("")
    repo_usage = defaultdict(int)
    for service in services:
        for repo in service.repository_deps:
            repo_usage[repo] += 1

    if repo_usage:
        report.append("最常用的 Repository:")
        sorted_repos = sorted(repo_usage.items(), key=lambda x: x[1], reverse=True)
        for repo, count in sorted_repos[:10]:
            report.append(f"  - {repo}: 被 {count} 个服务使用")
        report.append("")

    # 7. 详细服务列表
    report.append("## 7. 所有服务列表")
    report.append("")
    services_sorted = sorted(services, key=lambda s: len(s.methods), reverse=True)
    for service in services_sorted:
        report.append(f"### {service.name}")
        report.append(f"  文件: {service.file_path.relative_to(service.file_path.parents[2])}")
        report.append(f"  方法数: {len(service.methods)}")
        report.append(f"  代码行数: {service.total_lines}")
        report.append(f"  服务依赖: {len(service.dependencies)}")
        report.append(f"  Repository 依赖: {len(service.repository_deps)}")
        if service.methods:
            report.append(f"  方法列表:")
            for method in service.methods[:10]:  # 只显示前 10 个
                params_str = ', '.join(method.params) if method.params else ''
                report.append(f"    - {method.name}({params_str}) [{method.line_count} 行]")
        report.append("")

    # 写入文件
    output_path.write_text('\n'.join(report), encoding='utf-8')
    print(f"✅ 报告已生成: {output_path}")


def main():
    # 确定 quantsys-v2 根目录
    script_dir = Path(__file__).parent
    quantsys_root = script_dir.parent
    services_dir = quantsys_root / "application" / "services"

    if not services_dir.exists():
        print(f"❌ Services 目录不存在: {services_dir}")
        sys.exit(1)

    print(f"📂 扫描服务目录: {services_dir}")
    print()

    # 分析服务
    services = analyze_services_directory(services_dir)

    print(f"✅ 扫描完成，发现 {len(services)} 个服务")
    print()

    # 生成报告
    output_path = script_dir / "service_responsibility_audit.txt"
    generate_report(services, output_path)

    # 打印摘要
    print()
    print("=" * 80)
    print("摘要")
    print("=" * 80)
    print(f"总服务数: {len(services)}")
    total_methods = sum(len(s.methods) for s in services)
    print(f"总方法数: {total_methods}")

    granularity = analyze_service_granularity(services)
    print(f"上帝服务: {len(granularity['god_service'])} 个")
    print(f"职责过重: {len(granularity['too_large'])} 个")
    print(f"可能过度拆分: {len(granularity['too_small'])} 个")
    print(f"粒度合适: {len(granularity['appropriate'])} 个")

    overlaps = detect_responsibility_overlap(services)
    print(f"职责重叠: {len(overlaps)} 处")

    complex_methods = analyze_method_complexity(services)
    print(f"复杂方法 (>50行): {len(complex_methods)} 个")

    dep_graph = build_service_dependency_graph(services)
    cycles = detect_circular_dependencies(dep_graph)
    print(f"循环依赖: {len(cycles)} 个")


if __name__ == "__main__":
    main()
