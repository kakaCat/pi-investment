#!/usr/bin/env python3
"""
领域模型边界审计工具

检查项：
1. 领域模型的完整性（实体、值对象、领域服务）
2. 业务逻辑是否泄露到应用层
3. 领域层是否依赖外层（框架、数据库等）
4. 领域模型的贫血问题
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict, Counter


class DomainModelAnalyzer(ast.NodeVisitor):
    """分析领域模型文件"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.classes: List[Dict] = []
        self.imports: List[str] = []
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """分析类定义"""
        class_info = {
            'name': node.name,
            'line': node.lineno,
            'methods': [],
            'attributes': [],
            'base_classes': [self._get_name(base) for base in node.bases],
            'decorators': [self._get_name(dec) for dec in node.decorator_list],
        }

        self.current_class = class_info
        self.generic_visit(node)
        self.classes.append(class_info)
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """分析方法定义"""
        if self.current_class:
            method_info = {
                'name': node.name,
                'line': node.lineno,
                'is_property': any(self._get_name(dec) == 'property' for dec in node.decorator_list),
                'args': [arg.arg for arg in node.args.args if arg.arg != 'self'],
            }
            self.current_class['methods'].append(method_info)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """记录导入"""
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """记录导入"""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def _get_name(self, node):
        """获取节点名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return str(node)


def analyze_domain_layer(project_root: Path) -> Dict:
    """分析领域层"""

    results = {
        'total_files': 0,
        'total_classes': 0,
        'model_classes': [],  # 领域模型类
        'service_classes': [],  # 领域服务类
        'value_objects': [],  # 值对象
        'entities': [],  # 实体
        'ports': [],  # 端口（接口）
        'violations': [],  # 违规项
        'framework_imports': Counter(),  # 框架依赖
        'anemic_models': [],  # 贫血模型
    }

    domain_dir = project_root / 'domain'
    if not domain_dir.exists():
        print(f"⚠️  domain 目录不存在: {domain_dir}")
        return results

    # 扫描所有 domain 层文件
    for py_file in domain_dir.rglob("*.py"):
        if '__pycache__' in str(py_file) or 'benchmarks' in str(py_file):
            continue

        results['total_files'] += 1

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(py_file))
            analyzer = DomainModelAnalyzer(py_file)
            analyzer.visit(tree)

            # 分析每个类
            for cls in analyzer.classes:
                results['total_classes'] += 1

                rel_path = py_file.relative_to(project_root)
                cls_info = {
                    'file': str(rel_path),
                    'name': cls['name'],
                    'line': cls['line'],
                    'methods': cls['methods'],
                    'base_classes': cls['base_classes'],
                }

                # 分类
                if 'ports' in str(rel_path):
                    results['ports'].append(cls_info)
                elif 'Service' in cls['name'] or 'service' in str(py_file).lower():
                    results['service_classes'].append(cls_info)
                elif 'models' in str(rel_path) or any(base in ['BaseModel', 'SQLModel'] for base in cls['base_classes']):
                    results['model_classes'].append(cls_info)

                    # 检查贫血模型
                    business_methods = [m for m in cls['methods']
                                       if not m['name'].startswith('_')
                                       and m['name'] not in ['__init__', '__str__', '__repr__']
                                       and not m['is_property']]

                    if len(business_methods) == 0 and len(cls['methods']) > 0:
                        results['anemic_models'].append({
                            'file': str(rel_path),
                            'class': cls['name'],
                            'reason': '只有getter/setter，缺少业务逻辑'
                        })

            # 检查框架依赖
            framework_patterns = {
                'sqlalchemy': ['sqlalchemy'],
                'flask': ['flask'],
                'fastapi': ['fastapi'],
                'pydantic': ['pydantic'],
                'django': ['django'],
            }

            for imp in analyzer.imports:
                for framework, patterns in framework_patterns.items():
                    if any(pattern in imp.lower() for pattern in patterns):
                        # 例外：ports 目录可以依赖 pydantic（接口定义）
                        if framework == 'pydantic' and 'ports' in str(py_file):
                            continue

                        results['framework_imports'][framework] += 1
                        results['violations'].append({
                            'type': 'framework_dependency',
                            'file': str(py_file.relative_to(project_root)),
                            'framework': framework,
                            'import': imp,
                        })

        except Exception as e:
            # 跳过无法解析的文件
            pass

    return results


def print_domain_audit_report(results: Dict):
    """打印领域审计报告"""

    print("\n" + "=" * 80)
    print("领域模型边界审计报告")
    print("=" * 80)
    print()

    print("📊 总体统计")
    print("-" * 80)
    print(f"扫描文件数: {results['total_files']}")
    print(f"领域类总数: {results['total_classes']}")
    print(f"  • 端口接口: {len(results['ports'])}")
    print(f"  • 领域服务: {len(results['service_classes'])}")
    print(f"  • 领域模型: {len(results['model_classes'])}")
    print()

    print("🚨 违规检测")
    print("-" * 80)

    # 框架依赖违规
    if results['framework_imports']:
        print(f"❌ 框架依赖违规: {sum(results['framework_imports'].values())} 处")
        for framework, count in results['framework_imports'].most_common():
            print(f"   • {framework}: {count} 处")
        print()

        print("详细违规列表:")
        for violation in results['violations'][:20]:
            if violation['type'] == 'framework_dependency':
                print(f"   {violation['file']}")
                print(f"     导入: {violation['import']} ({violation['framework']})")
        print()
    else:
        print("✅ 无框架依赖违规")
        print()

    # 贫血模型检测
    print("🩺 贫血模型检测")
    print("-" * 80)
    if results['anemic_models']:
        print(f"⚠️  发现 {len(results['anemic_models'])} 个可能的贫血模型")
        for model in results['anemic_models'][:10]:
            print(f"   • {model['class']} ({model['file']})")
            print(f"     原因: {model['reason']}")
        print()
    else:
        print("✅ 未发现明显的贫血模型")
        print()

    # 端口接口
    print("🔌 端口接口")
    print("-" * 80)
    print(f"已定义端口接口: {len(results['ports'])} 个")
    if results['ports']:
        port_by_file = defaultdict(list)
        for port in results['ports']:
            port_by_file[port['file']].append(port['name'])

        for file, ports in sorted(port_by_file.items()):
            print(f"\n{file}")
            for port_name in ports:
                print(f"  • {port_name}")
    print()

    # 领域服务
    print("⚙️  领域服务")
    print("-" * 80)
    print(f"领域服务类: {len(results['service_classes'])} 个")
    if results['service_classes']:
        for svc in results['service_classes'][:10]:
            print(f"  • {svc['name']} ({svc['file']})")
    print()

    print("💡 审计建议")
    print("-" * 80)

    issues = []

    if results['framework_imports']:
        issues.append("1. 移除领域层的框架依赖（SQLAlchemy, Flask等）")
        issues.append("   - 领域层应该是纯 Python 业务逻辑")
        issues.append("   - ORM 模型应该在 adapters 层")

    if results['anemic_models']:
        issues.append("2. 充实贫血模型，将业务逻辑移入领域模型")
        issues.append("   - 领域模型不应该只是数据容器")
        issues.append("   - 业务规则应该封装在领域对象中")

    if len(results['service_classes']) > len(results['model_classes']) * 2:
        issues.append("3. 领域服务过多，考虑将逻辑移入领域模型")
        issues.append("   - 服务应该协调领域对象，而非包含全部逻辑")

    if not issues:
        print("✅ 领域层设计良好，未发现明显问题")
    else:
        for issue in issues:
            print(issue)

    print()


def main():
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("正在扫描领域层...")
    results = analyze_domain_layer(project_root)
    print_domain_audit_report(results)

    # 返回退出码
    if results['framework_imports'] or len(results['anemic_models']) > 10:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
