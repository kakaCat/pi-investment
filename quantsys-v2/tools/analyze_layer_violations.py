#!/usr/bin/env python3
"""
分层架构违规深度分析工具

分析 application → adapters 违规的具体模式和原因
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter


class DetailedImportAnalyzer(ast.NodeVisitor):
    """详细分析导入语句"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: List[Tuple[int, str, str]] = []  # (line_num, imported_module, import_type)

    def visit_Import(self, node: ast.Import):
        """处理 import xxx 语句"""
        for alias in node.names:
            self.imports.append((node.lineno, alias.name, 'import'))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """处理 from xxx import yyy 语句"""
        if node.module:
            module_parts = node.module.split('.')
            import_type = f"from {node.module}"
            self.imports.append((node.lineno, node.module, import_type))
        self.generic_visit(node)


def analyze_violation_patterns(project_root: Path) -> Dict:
    """深度分析违规模式"""

    results = {
        'total_violations': 0,
        'files_with_violations': 0,
        'violation_by_adapter_type': Counter(),
        'violation_by_service': Counter(),
        'detailed_violations': [],
        'most_imported_adapters': Counter(),
        'violation_locations': defaultdict(list),  # adapter_module -> [(service, line, import_statement)]
    }

    # 扫描所有 application 层文件
    app_dir = project_root / 'application'
    if not app_dir.exists():
        print(f"⚠️  application 目录不存在: {app_dir}")
        return results

    for py_file in app_dir.rglob("*.py"):
        if '__pycache__' in str(py_file):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(py_file))
            analyzer = DetailedImportAnalyzer(py_file)
            analyzer.visit(tree)

            file_violations = []

            for line_num, imported_module, import_type in analyzer.imports:
                # 检查是否导入了 adapters
                if imported_module.startswith('adapters'):
                    results['total_violations'] += 1

                    # 分类统计
                    module_parts = imported_module.split('.')
                    if len(module_parts) >= 2:
                        adapter_category = module_parts[1]  # inbound/outbound/shared
                        results['violation_by_adapter_type'][adapter_category] += 1

                        if len(module_parts) >= 3:
                            adapter_specific = '.'.join(module_parts[:3])
                            results['most_imported_adapters'][adapter_specific] += 1

                    # 记录详细信息
                    service_name = py_file.relative_to(app_dir).with_suffix('')
                    results['violation_by_service'][str(service_name)] += 1

                    file_violations.append({
                        'line': line_num,
                        'imported': imported_module,
                        'import_type': import_type
                    })

                    results['violation_locations'][imported_module].append(
                        (str(service_name), line_num, import_type)
                    )

            if file_violations:
                results['files_with_violations'] += 1
                results['detailed_violations'].append({
                    'file': str(py_file.relative_to(project_root)),
                    'violations': file_violations
                })

        except Exception as e:
            # 跳过无法解析的文件
            pass

    return results


def print_analysis_report(results: Dict):
    """打印详细分析报告"""

    print("=" * 80)
    print("分层架构违规深度分析报告")
    print("=" * 80)
    print()

    print("📊 总体统计")
    print("-" * 80)
    print(f"违规导入总数: {results['total_violations']}")
    print(f"违规文件数量: {results['files_with_violations']}")
    print(f"平均每文件违规数: {results['total_violations'] / max(results['files_with_violations'], 1):.1f}")
    print()

    print("📁 按适配器类型分类")
    print("-" * 80)
    for adapter_type, count in results['violation_by_adapter_type'].most_common():
        percentage = (count / results['total_violations']) * 100
        print(f"{adapter_type:20s}: {count:4d} ({percentage:5.1f}%)")
    print()

    print("🔝 最常被导入的适配器模块 (Top 20)")
    print("-" * 80)
    for adapter, count in results['most_imported_adapters'].most_common(20):
        print(f"{adapter:50s}: {count:3d}")
    print()

    print("🔥 违规最多的服务文件 (Top 20)")
    print("-" * 80)
    for service, count in results['violation_by_service'].most_common(20):
        print(f"{service:50s}: {count:3d}")
    print()

    print("📋 典型违规示例 (前10个文件)")
    print("-" * 80)
    for i, violation in enumerate(results['detailed_violations'][:10], 1):
        print(f"\n{i}. {violation['file']}")
        for v in violation['violations'][:5]:  # 每个文件只显示前5个违规
            print(f"   L{v['line']:4d}: {v['import_type']}")
        if len(violation['violations']) > 5:
            print(f"   ... 还有 {len(violation['violations']) - 5} 个违规")
    print()

    print("🎯 重构优先级建议")
    print("-" * 80)
    print()

    # 分析哪些适配器被最多服务依赖
    print("1️⃣  高优先级 - 被大量服务依赖的适配器（需要提取接口）:")
    print()
    high_priority = [(adapter, len(locations))
                     for adapter, locations in results['violation_locations'].items()
                     if len(locations) >= 10]
    high_priority.sort(key=lambda x: x[1], reverse=True)

    for adapter, service_count in high_priority[:10]:
        print(f"   • {adapter}")
        print(f"     被 {service_count} 个服务依赖")
    print()

    # 分析哪些服务违规最严重
    print("2️⃣  中优先级 - 违规最严重的服务（需要重构）:")
    print()
    for service, count in results['violation_by_service'].most_common(10):
        if count >= 5:
            print(f"   • {service}")
            print(f"     {count} 个违规导入")
    print()

    print("3️⃣  低优先级 - 少量违规的服务（可以逐步改进）")
    print(f"   • {sum(1 for c in results['violation_by_service'].values() if c <= 2)} 个服务只有 1-2 个违规")
    print()


def analyze_adapter_usage_patterns(project_root: Path):
    """分析适配器使用模式，找出最常见的使用场景"""

    print("=" * 80)
    print("适配器使用模式分析")
    print("=" * 80)
    print()

    patterns = {
        'database': [],
        'external_api': [],
        'broker': [],
        'fastapi': [],
        'shared': [],
        'other': []
    }

    app_dir = project_root / 'application'

    for py_file in app_dir.rglob("*.py"):
        if '__pycache__' in str(py_file):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单模式匹配
            if 'from adapters.outbound.datasources' in content:
                patterns['external_api'].append(str(py_file.relative_to(project_root)))
            if 'from adapters.outbound.brokers' in content:
                patterns['broker'].append(str(py_file.relative_to(project_root)))
            if 'from adapters.inbound.fastapi_app' in content:
                patterns['fastapi'].append(str(py_file.relative_to(project_root)))
            if 'from adapters.shared' in content:
                patterns['shared'].append(str(py_file.relative_to(project_root)))

        except:
            pass

    print("📊 使用场景分类:")
    print()
    for pattern_type, files in patterns.items():
        if files:
            print(f"{pattern_type:20s}: {len(files)} 个文件")
    print()


def main():
    project_root = Path(__file__).parent.parent

    print("\n正在扫描项目...\n")
    results = analyze_violation_patterns(project_root)

    print_analysis_report(results)

    print("\n")
    analyze_adapter_usage_patterns(project_root)

    print("=" * 80)
    print("分析完成")
    print("=" * 80)


if __name__ == "__main__":
    sys.exit(main())
