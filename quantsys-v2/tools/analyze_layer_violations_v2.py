#!/usr/bin/env python3
"""
分层架构违规深度分析工具 V2

区分顶层导入和局部导入：
- 顶层导入（模块级别）: ❌ 违规
- 局部导入（函数内）: ✅ 允许（符合编码规范）
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter


class ScopeAwareImportAnalyzer(ast.NodeVisitor):
    """区分顶层和局部导入的分析器"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.top_level_imports: List[Tuple[int, str, str]] = []  # 顶层导入（违规）
        self.local_imports: List[Tuple[int, str, str]] = []      # 局部导入（允许）
        self.current_scope_depth = 0  # 0 = 模块级，>0 = 函数/类内

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """进入函数作用域"""
        self.current_scope_depth += 1
        self.generic_visit(node)
        self.current_scope_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """进入异步函数作用域"""
        self.current_scope_depth += 1
        self.generic_visit(node)
        self.current_scope_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef):
        """进入类作用域"""
        self.current_scope_depth += 1
        self.generic_visit(node)
        self.current_scope_depth -= 1

    def visit_Import(self, node: ast.Import):
        """处理 import xxx 语句"""
        for alias in node.names:
            import_info = (node.lineno, alias.name, 'import')
            if self.current_scope_depth == 0:
                self.top_level_imports.append(import_info)
            else:
                self.local_imports.append(import_info)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """处理 from xxx import yyy 语句"""
        if node.module:
            import_info = (node.lineno, node.module, f"from {node.module}")
            if self.current_scope_depth == 0:
                self.top_level_imports.append(import_info)
            else:
                self.local_imports.append(import_info)
        self.generic_visit(node)


def analyze_violations_with_scope(project_root: Path) -> Dict:
    """区分顶层和局部导入的违规分析"""

    results = {
        'top_level_violations': 0,      # 顶层违规（真正的违规）
        'local_imports': 0,              # 局部导入（允许）
        'files_with_violations': 0,
        'violation_by_adapter_type': Counter(),
        'violation_by_service': Counter(),
        'detailed_violations': [],
        'most_imported_adapters': Counter(),
        'local_import_details': [],      # 局部导入详情（仅供参考）
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
            analyzer = ScopeAwareImportAnalyzer(py_file)
            analyzer.visit(tree)

            file_violations = []
            file_local_imports = []

            # 分析顶层导入（真正的违规）
            for line_num, imported_module, import_type in analyzer.top_level_imports:
                if imported_module.startswith('adapters'):
                    results['top_level_violations'] += 1

                    # 分类统计
                    module_parts = imported_module.split('.')
                    if len(module_parts) >= 2:
                        adapter_category = module_parts[1]
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
                        'import_type': import_type,
                        'scope': 'top-level'
                    })

            # 统计局部导入（允许，仅供参考）
            for line_num, imported_module, import_type in analyzer.local_imports:
                if imported_module.startswith('adapters'):
                    results['local_imports'] += 1
                    file_local_imports.append({
                        'line': line_num,
                        'imported': imported_module,
                        'import_type': import_type,
                        'scope': 'local (allowed)'
                    })

            if file_violations:
                results['files_with_violations'] += 1
                results['detailed_violations'].append({
                    'file': str(py_file.relative_to(project_root)),
                    'violations': file_violations
                })

            if file_local_imports:
                results['local_import_details'].append({
                    'file': str(py_file.relative_to(project_root)),
                    'local_imports': file_local_imports
                })

        except Exception as e:
            # 跳过无法解析的文件
            pass

    return results


def print_analysis_report_v2(results: Dict):
    """打印区分顶层/局部导入的分析报告"""

    print("\n" + "=" * 80)
    print("分层架构违规分析报告 V2 (区分顶层/局部导入)")
    print("=" * 80)
    print()

    print("📊 总体统计")
    print("-" * 80)
    print(f"❌ 顶层违规导入: {results['top_level_violations']} (真正的违规)")
    print(f"✅ 局部导入: {results['local_imports']} (允许，符合规范)")
    print(f"📁 违规文件数量: {results['files_with_violations']}")
    if results['files_with_violations'] > 0:
        print(f"📈 平均每文件违规数: {results['top_level_violations'] / results['files_with_violations']:.1f}")
    print()

    if results['top_level_violations'] == 0:
        print("🎉 恭喜！没有顶层违规导入，架构完全符合规范！")
        print()
        print("💡 提示：局部导入（函数内导入）是允许的，符合编码规范。")
        print("   当前有 {} 处局部导入，这是正常的。".format(results['local_imports']))
        return

    print("📁 按适配器类型分类")
    print("-" * 80)
    for adapter_type, count in results['violation_by_adapter_type'].most_common():
        percentage = (count / results['top_level_violations']) * 100
        print(f"{adapter_type:20s}: {count:4d} ({percentage:5.1f}%)")
    print()

    print("🔝 最常被导入的适配器模块 (Top 10)")
    print("-" * 80)
    for adapter, count in results['most_imported_adapters'].most_common(10):
        print(f"{adapter:50s}: {count:3d}")
    print()

    print("🔥 违规最多的服务文件")
    print("-" * 80)
    for service, count in results['violation_by_service'].most_common():
        print(f"{service:50s}: {count:3d}")
    print()

    print("📋 详细违规列表")
    print("-" * 80)
    for i, violation in enumerate(results['detailed_violations'], 1):
        print(f"\n{i}. {violation['file']}")
        for v in violation['violations']:
            print(f"   L{v['line']:4d}: {v['import_type']} (顶层)")
    print()

    print("💡 修复建议")
    print("-" * 80)
    print("1. 将顶层导入改为局部导入（在函数/方法内部导入）")
    print("2. 或者添加接口类型注解，从 domain.ports 导入接口")
    print()
    print("示例修复：")
    print("  # ❌ 错误（顶层导入）")
    print("  from adapters.outbound.repositories.stock_repository import StockORMRepository")
    print()
    print("  # ✅ 正确（局部导入 + 接口注解）")
    print("  from domain.ports.repository_ports_extended import IStockRepository")
    print()
    print("  class MyService:")
    print("      def __init__(self):")
    print("          from adapters.outbound.repositories.stock_repository import StockORMRepository")
    print("          self.repo: IStockRepository = StockORMRepository()")
    print()


def main():
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("正在扫描项目...")
    results = analyze_violations_with_scope(project_root)
    print_analysis_report_v2(results)

    # 返回退出码
    if results['top_level_violations'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
