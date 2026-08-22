#!/usr/bin/env python3
"""
批量分析服务的依赖注入重构需求

用于识别需要重构的服务及其依赖模式
"""
import ast
import os
from pathlib import Path
from typing import List, Dict, Tuple
import json


class ServiceAnalyzer(ast.NodeVisitor):
    """分析服务类的依赖模式"""

    def __init__(self):
        self.class_name = None
        self.init_params = []
        self.direct_instantiations = []
        self.in_init = False

    def visit_ClassDef(self, node):
        self.class_name = node.name
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name == '__init__':
            self.in_init = True
            # 收集构造函数参数
            for arg in node.args.args:
                if arg.arg != 'self':
                    self.init_params.append(arg.arg)
            self.generic_visit(node)
            self.in_init = False
        else:
            self.generic_visit(node)

    def is_inside_conditional(self, node):
        """检查节点是否在条件语句内部（if/else）"""
        # 简化版本：检查父节点是否为 If
        # 在实际AST遍历中，我们需要更复杂的逻辑
        return False  # 暂时简化处理

    def visit_Assign(self, node):
        if self.in_init and isinstance(node.value, ast.Call):
            # 检测直接实例化
            if isinstance(node.value.func, ast.Name):
                class_name = node.value.func.id
                if class_name.startswith('I') or 'Service' in class_name:
                    # 提取被赋值的属性名
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            attr_name = target.attr
                            self.direct_instantiations.append({
                                'attr': attr_name,
                                'class': class_name,
                                'line': node.lineno
                            })
        self.generic_visit(node)

    def visit_If(self, node):
        """访问 If 节点，跳过 else 分支中的回退实例化"""
        if self.in_init:
            # 访问条件表达式
            self.visit(node.test)
            # 访问 if 主体
            for child in node.body:
                self.visit(child)
            # 跳过 else/elif 分支（这些通常是回退逻辑）
            # 不访问 node.orelse
        else:
            self.generic_visit(node)


def analyze_service_file(file_path: Path) -> Dict:
    """分析单个服务文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        analyzer = ServiceAnalyzer()
        analyzer.visit(tree)

        return {
            'file': str(file_path),
            'class_name': analyzer.class_name,
            'init_params': analyzer.init_params,
            'direct_instantiations': analyzer.direct_instantiations,
            'needs_refactor': len(analyzer.direct_instantiations) > 0
        }
    except Exception as e:
        return {
            'file': str(file_path),
            'error': str(e)
        }


def scan_services_directory(base_dir: str) -> List[Dict]:
    """扫描 services 目录下的所有服务"""
    services_dir = Path(base_dir) / 'application' / 'services'
    results = []

    for py_file in services_dir.glob('*.py'):
        if py_file.name.startswith('__'):
            continue

        result = analyze_service_file(py_file)
        if result.get('needs_refactor'):
            results.append(result)

    return results


def generate_refactor_plan(results: List[Dict]) -> str:
    """生成重构计划"""
    # 按直接实例化数量排序
    results.sort(key=lambda x: len(x.get('direct_instantiations', [])), reverse=True)

    plan = "# 批量重构计划\n\n"
    plan += f"总计: {len(results)} 个服务需要重构\n\n"

    for i, result in enumerate(results, 1):
        instantiations = result.get('direct_instantiations', [])
        plan += f"## {i}. {Path(result['file']).name}\n"
        plan += f"- 类名: {result.get('class_name', 'N/A')}\n"
        plan += f"- 问题数: {len(instantiations)}\n"
        plan += f"- 当前参数: {', '.join(result.get('init_params', []))}\n"

        if instantiations:
            plan += "- 需要注入的依赖:\n"
            for inst in instantiations:
                plan += f"  - `{inst['attr']}`: {inst['class']} (line {inst['line']})\n"

        plan += "\n"

    return plan


if __name__ == '__main__':
    import sys

    base_dir = sys.argv[1] if len(sys.argv) > 1 else '.'

    print("扫描服务目录...")
    results = scan_services_directory(base_dir)

    print(f"\n找到 {len(results)} 个需要重构的服务\n")

    # 生成重构计划
    plan = generate_refactor_plan(results)

    # 输出到文件
    output_file = 'refactor-plan.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(plan)

    print(f"重构计划已保存到: {output_file}")

    # 输出到控制台（前10个）
    print("\n前10个优先级最高的服务:")
    for result in results[:10]:
        instantiations = result.get('direct_instantiations', [])
        print(f"  {Path(result['file']).name}: {len(instantiations)} 个依赖")
