#!/usr/bin/env python3
"""
服务层仓储导入迁移工具

自动将 application 层的导入从具体实现迁移到接口：
  from adapters.outbound.repositories import XxxRepository
→ from domain.ports import IXxxRepository
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# 映射表：适配器实现类 → 端口接口
REPOSITORY_MAPPING = {
    # 核心仓储
    'StrategyORMRepository': 'IStrategyRepository',
    'SignalORMRepository': 'ISignalRepository',
    'SignalAsyncORMRepository': 'ISignalRepository',
    'KlineORMRepository': 'IKlineRepository',
    'PortfolioORMRepository': 'IPortfolioRepository',
    'RiskORMRepository': 'IRiskRepository',
    'FactorORMRepository': 'IFactorRepository',

    # 异步仓储
    'SignalAsyncRepository': 'ISignalRepository',
    'DailyKlineAsyncRepository': 'IAsyncKlineRepository',
    'FactorAsyncRepository': 'IAsyncFactorRepository',
    'BacktestAsyncRepository': 'IBacktestRepository',
    'StockAsyncRepository': 'IStockRepository',
    'StockPoolAsyncRepository': 'IStockPoolRepository',
    'StrategyAsyncRepository': 'IStrategyRepository',
    'PortfolioAsyncRepository': 'IPortfolioRepository',
    'RiskAsyncRepository': 'IRiskRepository',

    # 业务仓储
    'StockORMRepository': 'IStockRepository',
    'StockPoolORMRepository': 'IStockPoolRepository',
    'StockPoolRepository': 'IStockPoolRepository',
    'PoolORMRepository': 'IPoolRepository',
    'PositionORMRepository': 'IPositionRepository',
    'OrderORMRepository': 'IOrderRepository',
    'SimulationRepository': 'ISimulationRepository',
    'SimulationORMRepository': 'ISimulationRepository',
    'BacktestORMRepository': 'IBacktestRepository',
    'FinancialORMRepository': 'IFinancialRepository',
    'FinancialRepository': 'IFinancialRepository',
    'FundFlowORMRepository': 'IFundFlowRepository',
    'FundFlowRepository': 'IFundFlowRepository',

    # 配置和执行
    'RiskConfigORMRepository': 'IRiskConfigRepository',
    'SchedulerConfigORMRepository': 'ISchedulerConfigRepository',
    'SchedulerRepository': 'ISchedulerRepository',
    'StrategyPerformanceORMRepository': 'IStrategyPerformanceRepository',
    'StrategyWeightORMRepository': 'IStrategyWeightRepository',
    'StrategyCircuitBreakerORMRepository': 'IStrategyCircuitBreakerRepository',
    'SignalExecutionORMRepository': 'ISignalExecutionRepository',
    'SignalExecutionLogORMRepository': 'ISignalExecutionLogRepository',

    # Agent 相关
    'AgentIntelligenceORMRepository': 'IAgentIntelligenceRepository',
    'AgentKnowledgeORMRepository': 'IAgentKnowledgeRepository',
    'AgentDecisionRepository': 'IAgentDecisionRepository',

    # 其他
    'HeatmapRepository': 'IHeatmapRepository',
    'DecisionORMRepository': 'IDecisionRepository',
    'ConditionRuleORMRepository': 'IConditionRuleRepository',
    'ConditionResultORMRepository': 'IConditionResultRepository',
    'PoolChangeLogRepository': 'IPoolChangeLogRepository',
}


def analyze_file(file_path: Path) -> Dict:
    """分析文件中的仓储导入"""
    result = {
        'file': str(file_path),
        'imports_to_migrate': [],
        'imports_unknown': [],
        'needs_migration': False
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            # 匹配 from adapters.outbound.repositories import XXX
            match = re.match(
                r'^from\s+adapters\.outbound\.repositories(?:\.\w+)?\s+import\s+(.+)',
                line.strip()
            )

            if match:
                imported = match.group(1).strip()

                # 处理多个导入
                imports = [imp.strip() for imp in imported.split(',')]

                for imp in imports:
                    # 移除 as 别名
                    actual_import = imp.split(' as ')[0].strip()

                    if actual_import in REPOSITORY_MAPPING:
                        result['imports_to_migrate'].append({
                            'line_num': i,
                            'line': line.strip(),
                            'old_import': actual_import,
                            'new_import': REPOSITORY_MAPPING[actual_import],
                            'has_alias': ' as ' in imp
                        })
                        result['needs_migration'] = True
                    else:
                        result['imports_unknown'].append({
                            'line_num': i,
                            'line': line.strip(),
                            'import': actual_import
                        })

    except Exception as e:
        result['error'] = str(e)

    return result


def migrate_file(file_path: Path, dry_run: bool = True) -> bool:
    """迁移单个文件"""

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        migrations_made = []

        # 1. 替换导入语句
        for old_name, new_name in REPOSITORY_MAPPING.items():
            # 匹配整行导入
            pattern = rf'from\s+adapters\.outbound\.repositories(?:\.\w+)?\s+import\s+{old_name}'
            replacement = f'from domain.ports import {new_name}'

            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                migrations_made.append(f"{old_name} → {new_name}")

        # 2. 替换代码中的使用（类名）
        for old_name, new_name in REPOSITORY_MAPPING.items():
            # 替换类型注解和实例化
            content = re.sub(rf'\b{old_name}\b', new_name, content)

        # 3. 清理可能的重复导入
        # 收集所有 domain.ports 导入
        port_imports = set()
        for match in re.finditer(r'from domain\.ports import (.+)', content):
            imports = match.group(1).split(',')
            for imp in imports:
                port_imports.add(imp.strip())

        # 如果有多个 from domain.ports import，合并它们
        if len(port_imports) > 1:
            # 移除所有旧的
            content = re.sub(r'from domain\.ports import .+\n', '', content)
            # 在文件开头添加合并后的导入
            combined_import = f"from domain.ports import {', '.join(sorted(port_imports))}\n"
            # 找到第一个导入语句的位置
            first_import_match = re.search(r'^(from|import)\s+', content, re.MULTILINE)
            if first_import_match:
                pos = first_import_match.start()
                content = content[:pos] + combined_import + content[pos:]

        if content != original_content:
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ {file_path.name}: 迁移成功")
                for migration in migrations_made:
                    print(f"   • {migration}")
            else:
                print(f"🔍 {file_path.name}: 需要迁移")
                for migration in migrations_made:
                    print(f"   • {migration}")
            return True

    except Exception as e:
        print(f"❌ {file_path.name}: 迁移失败 - {e}")
        return False

    return False


def scan_and_report(project_root: Path):
    """扫描并报告需要迁移的文件"""

    app_dir = project_root / 'application'
    if not app_dir.exists():
        print(f"❌ application 目录不存在: {app_dir}")
        return

    print("=" * 80)
    print("服务层仓储导入迁移分析")
    print("=" * 80)
    print()

    files_to_migrate = []
    unknown_imports = set()

    for py_file in app_dir.rglob("*.py"):
        if '__pycache__' in str(py_file):
            continue

        result = analyze_file(py_file)

        if result['needs_migration']:
            files_to_migrate.append(result)

        for unknown in result.get('imports_unknown', []):
            unknown_imports.add(unknown['import'])

    print(f"📊 扫描结果")
    print("-" * 80)
    print(f"需要迁移的文件: {len(files_to_migrate)}")
    print(f"未知的仓储类型: {len(unknown_imports)}")
    print()

    if files_to_migrate:
        print("📁 需要迁移的文件 (Top 20):")
        print("-" * 80)
        for i, result in enumerate(files_to_migrate[:20], 1):
            file_name = Path(result['file']).name
            count = len(result['imports_to_migrate'])
            print(f"{i:2d}. {file_name:50s} ({count} 个导入)")

        if len(files_to_migrate) > 20:
            print(f"    ... 还有 {len(files_to_migrate) - 20} 个文件")
        print()

    if unknown_imports:
        print("⚠️  未知的仓储类型（需要先在 ports 中定义接口）:")
        print("-" * 80)
        for imp in sorted(unknown_imports):
            print(f"   • {imp}")
        print()

    print("=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='迁移服务层的仓储导入')
    parser.add_argument('--mode', choices=['scan', 'migrate'], default='scan',
                       help='scan=仅扫描, migrate=执行迁移')
    parser.add_argument('--dry-run', action='store_true',
                       help='干运行模式（不实际修改文件）')
    parser.add_argument('--file', type=str,
                       help='只处理指定文件')

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    if args.mode == 'scan':
        scan_and_report(project_root)

    elif args.mode == 'migrate':
        app_dir = project_root / 'application'

        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"❌ 文件不存在: {file_path}")
                return 1

            migrate_file(file_path, dry_run=args.dry_run)

        else:
            # 批量迁移
            print("=" * 80)
            if args.dry_run:
                print("服务层仓储导入迁移 (DRY RUN)")
            else:
                print("服务层仓储导入迁移")
            print("=" * 80)
            print()

            migrated_count = 0

            for py_file in app_dir.rglob("*.py"):
                if '__pycache__' in str(py_file):
                    continue

                if migrate_file(py_file, dry_run=args.dry_run):
                    migrated_count += 1

            print()
            print("=" * 80)
            print(f"迁移完成: {migrated_count} 个文件")
            print("=" * 80)


if __name__ == "__main__":
    sys.exit(main())
