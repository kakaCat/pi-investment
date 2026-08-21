#!/usr/bin/env python3
"""
自动迁移工具：数据源导入从适配器层改为领域端口

将应用层的 datasource 导入从 adapters.outbound.datasources 改为 domain.ports.datasource_ports
"""

import re
from pathlib import Path
from typing import Dict, List

# 导入映射表：旧导入 -> (新模块, 新类名/函数名)
DATASOURCE_MAPPING = {
    # Manager 和工厂函数
    'get_data_provider_manager': ('domain.ports.datasource_ports', 'IDataProviderManager'),
    'get_data_source_manager': ('domain.ports.datasource_ports', 'IDataProviderManager'),
    'DataProviderManager': ('domain.ports.datasource_ports', 'IDataProviderManager'),

    # 基础设施组件
    'DataSourceCache': ('domain.ports.datasource_ports', 'ICacheService'),
    'CircuitBreaker': ('domain.ports.datasource_ports', 'ICircuitBreaker'),

    # 数据模型
    'QuoteData': ('domain.models.market_data', 'QuoteData'),
    'KlineData': ('domain.models.market_data', 'KlineData'),
    'FinancialData': ('domain.models.market_data', 'FinancialData'),
    'DividendData': ('domain.models.market_data', 'DividendData'),
    'MarketData': ('domain.models.market_data', 'MarketData'),
    'StockData': ('domain.models.market_data', 'StockData'),

    # 特定数据源
    'LhbDataSource': ('domain.ports.datasource_ports', 'ILhbDataSource'),
    'FundFlowDataSource': ('domain.ports.datasource_ports', 'IFundFlowDataSource'),
    'NorthHoldingsCCASSSource': ('domain.ports.datasource_ports', 'INorthFlowDataSource'),
}

# 需要特殊处理的导入模式
FACTORY_FUNCTIONS = {
    'get_data_provider_manager',
    'get_data_source_manager',
}


def analyze_file(file_path: Path) -> Dict:
    """分析文件中的 datasource 导入"""
    result = {
        'file': str(file_path),
        'imports_to_migrate': [],
        'factory_calls': [],
        'needs_migration': False
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        # 查找 datasource 导入
        for i, line in enumerate(lines, 1):
            # 匹配 from adapters.outbound.datasources[.xxx] import ...
            match = re.match(
                r'^(\s*)from\s+adapters\.outbound\.datasources(?:\.[\w.]+)?\s+import\s+(.+)',
                line.strip()
            )

            if match:
                indent, imported = match.groups()
                imported = imported.strip()

                # 处理多行导入
                if '(' in imported and ')' not in imported:
                    # 多行导入开始
                    j = i
                    while j < len(lines) and ')' not in lines[j]:
                        j += 1
                    if j < len(lines):
                        multi_line = '\n'.join(lines[i-1:j+1])
                        imports = re.findall(r'\b(\w+)\b', multi_line)
                        imports = [imp for imp in imports if imp not in ['from', 'import', 'adapters', 'outbound', 'datasources']]
                    else:
                        imports = []
                else:
                    # 单行导入
                    imports = [imp.strip() for imp in imported.replace('(', '').replace(')', '').split(',')]

                for imp in imports:
                    imp = imp.strip()
                    if imp in DATASOURCE_MAPPING:
                        result['imports_to_migrate'].append({
                            'line': i,
                            'old_name': imp,
                            'new_module': DATASOURCE_MAPPING[imp][0],
                            'new_name': DATASOURCE_MAPPING[imp][1]
                        })
                        result['needs_migration'] = True

        # 查找工厂函数调用（需要加类型注解）
        for func_name in FACTORY_FUNCTIONS:
            if func_name in content:
                result['factory_calls'].append(func_name)

    except Exception as e:
        result['error'] = str(e)

    return result


def migrate_file(file_path: Path, dry_run: bool = True) -> bool:
    """迁移单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        original_content = content
        modified = False

        # Step 1: 替换导入语句
        # 收集需要添加的新导入
        new_imports_ports = set()
        new_imports_models = set()
        lines_to_remove = []

        for i, line in enumerate(lines):
            # 匹配 from adapters.outbound.datasources import ...
            match = re.match(
                r'^(\s*)from\s+adapters\.outbound\.datasources(?:\.[\w.]+)?\s+import\s+(.+)',
                line
            )

            if match:
                indent, imported = match.groups()

                # 处理括号导入
                if '(' in imported:
                    # 找到对应的右括号
                    j = i
                    while j < len(lines) and ')' not in lines[j]:
                        j += 1

                    if j < len(lines):
                        # 提取所有导入
                        multi_line = '\n'.join(lines[i:j+1])
                        imports = re.findall(r'\b(\w+)\b', multi_line)
                        imports = [imp for imp in imports if imp not in ['from', 'import', 'adapters', 'outbound', 'datasources']]

                        # 标记这些行为待删除
                        lines_to_remove.extend(range(i, j+1))

                        # 添加到新导入
                        for imp in imports:
                            imp = imp.strip()
                            if imp in DATASOURCE_MAPPING:
                                module, name = DATASOURCE_MAPPING[imp]
                                if module == 'domain.ports.datasource_ports':
                                    new_imports_ports.add(name)
                                elif module == 'domain.models.market_data':
                                    new_imports_models.add(name)
                else:
                    # 单行导入
                    imports = [imp.strip() for imp in imported.replace('(', '').replace(')', '').split(',')]

                    lines_to_remove.append(i)

                    for imp in imports:
                        imp = imp.strip()
                        if imp in DATASOURCE_MAPPING:
                            module, name = DATASOURCE_MAPPING[imp]
                            if module == 'domain.ports.datasource_ports':
                                new_imports_ports.add(name)
                            elif module == 'domain.models.market_data':
                                new_imports_models.add(name)

        if lines_to_remove:
            # 移除旧导入
            new_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]

            # 在文件开头添加新导入（在其他 import 之后）
            insert_idx = 0
            for i, line in enumerate(new_lines):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    insert_idx = i + 1
                elif insert_idx > 0 and not line.strip().startswith('import ') and not line.strip().startswith('from '):
                    break

            imports_to_add = []
            if new_imports_ports:
                imports_to_add.append(f"from domain.ports.datasource_ports import {', '.join(sorted(new_imports_ports))}")
            if new_imports_models:
                imports_to_add.append(f"from domain.models.market_data import {', '.join(sorted(new_imports_models))}")

            if imports_to_add:
                new_lines = new_lines[:insert_idx] + imports_to_add + new_lines[insert_idx:]

            content = '\n'.join(new_lines)
            modified = True

        # Step 2: 添加类型注解到工厂函数调用
        # 例如：manager = get_data_provider_manager()
        #   -> manager: IDataProviderManager = get_data_provider_manager()
        for func_name in FACTORY_FUNCTIONS:
            if func_name in content:
                # 匹配赋值语句：var = get_data_provider_manager()
                pattern = r'(\s+)(\w+)\s*=\s*' + func_name + r'\(\)'
                replacement = r'\1\2: IDataProviderManager = ' + func_name + r'()'

                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    content = new_content
                    modified = True

        # Step 3: 添加具体实现的导入（工厂函数需要）
        if 'get_data_provider_manager' in content or 'get_data_source_manager' in content:
            if 'from adapters.outbound.datasources.manager import' not in content:
                # 在 domain 导入后添加 adapters 导入
                lines = content.split('\n')
                insert_idx = 0
                for i, line in enumerate(lines):
                    if 'from domain.ports.datasource_ports import' in line or 'from domain.models.market_data import' in line:
                        insert_idx = i + 1

                if insert_idx > 0:
                    lines.insert(insert_idx, 'from adapters.outbound.datasources.manager import get_data_provider_manager')
                    content = '\n'.join(lines)
                    modified = True

        if modified and not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return modified

    except Exception as e:
        print(f"❌ {file_path}: {e}")
        return False


def main():
    import sys

    dry_run = '--dry-run' in sys.argv
    mode = 'scan' if '--mode' not in ' '.join(sys.argv) else sys.argv[sys.argv.index('--mode') + 1]

    print(f"数据源导入迁移工具")
    print(f"模式: {'扫描' if mode == 'scan' or dry_run else '迁移'}")
    print()

    # 扫描所有服务文件
    services_dir = Path('application/services')
    service_files = list(services_dir.glob('**/*.py'))

    if mode == 'scan' or dry_run:
        # 扫描模式
        needs_migration = []
        for file_path in service_files:
            result = analyze_file(file_path)
            if result['needs_migration']:
                needs_migration.append(result)

        if needs_migration:
            print(f"发现 {len(needs_migration)} 个文件需要迁移:\n")
            for result in needs_migration:
                print(f"📄 {result['file']}")
                for imp in result['imports_to_migrate']:
                    print(f"   L{imp['line']}: {imp['old_name']} → {imp['new_name']}")
                if result['factory_calls']:
                    print(f"   工厂调用: {', '.join(result['factory_calls'])}")
                print()
        else:
            print("✅ 没有文件需要迁移")

    else:
        # 迁移模式
        migrated = []
        for file_path in service_files:
            result = analyze_file(file_path)
            if result['needs_migration']:
                if migrate_file(file_path, dry_run=False):
                    migrated.append(file_path)
                    print(f"✅ {file_path.name}: 迁移成功")
                    for imp in result['imports_to_migrate']:
                        print(f"   • {imp['old_name']} → {imp['new_name']}")

        print(f"\n{'='*80}")
        print(f"迁移完成: {len(migrated)} 个文件")
        print(f"{'='*80}")


if __name__ == '__main__':
    main()
