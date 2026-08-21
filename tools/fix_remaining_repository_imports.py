#!/usr/bin/env python3
"""
修复残留的 Repository 导入路径

将从 adapters.outbound.repositories.* 导入接口
改为从 domain.ports.repository_ports_extended 导入
"""

import re
from pathlib import Path
from typing import List, Tuple

# 需要修复的文件及其导入
FILES_TO_FIX = [
    ('application/services/strategy_service.py', 'simulation_repository', 'ISimulationRepository'),
    ('application/services/knowledge_service.py', 'agent_knowledge_repository', 'IAgentKnowledgeRepository'),
    ('application/services/watch_engine/factory.py', 'watch_rule_repository', 'IWatchRuleRepository'),
    ('application/services/evolution/evolution_fitness_service.py', 'evolution_fitness_repository', 'IEvolutionFitnessRepository'),
    ('application/services/evolution/decision_score_service.py', 'agent_intelligence_repository', 'IAgentIntelligenceRepository'),
    ('application/services/evolution/missed_opportunity_service.py', 'agent_intelligence_repository', 'IAgentIntelligenceRepository'),
]


def fix_file(file_path: str, repo_module: str, interface_name: str, dry_run: bool = False) -> bool:
    """修复单个文件的导入路径"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  文件不存在: {file_path}")
        return False

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 模式1: from adapters.outbound.repositories.xxx_repository import (IXxxRepository)
        old_import_pattern = f'from adapters.outbound.repositories.{repo_module} import'
        new_import = 'from domain.ports.repository_ports_extended import'

        if old_import_pattern in content:
            # 替换导入语句
            content = content.replace(old_import_pattern, new_import)

            if content != original_content:
                if not dry_run:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                print(f"✅ {path.name}")
                print(f"   {old_import_pattern}")
                print(f"   → {new_import}")
                return True
            else:
                print(f"⏭️  {path.name} (无需修改)")
                return False
        else:
            print(f"⚠️  {path.name}: 未找到预期的导入语句")
            return False

    except Exception as e:
        print(f"❌ {path}: {e}")
        return False


def analyze_missing_interfaces():
    """分析是否有接口定义缺失"""
    print("\n检查接口定义...")

    interfaces_to_check = [
        'ISimulationRepository',
        'IAgentKnowledgeRepository',
        'IWatchRuleRepository',
        'IEvolutionFitnessRepository',
        'IAgentIntelligenceRepository',
    ]

    ports_file = Path('domain/ports/repository_ports_extended.py')
    if not ports_file.exists():
        print("❌ domain/ports/repository_ports_extended.py 不存在")
        return

    with open(ports_file, 'r', encoding='utf-8') as f:
        content = f.read()

    missing = []
    for interface in interfaces_to_check:
        if f'class {interface}' not in content:
            missing.append(interface)

    if missing:
        print(f"⚠️  缺失接口定义: {', '.join(missing)}")
        return missing
    else:
        print("✅ 所有接口都已定义")
        return []


def main():
    import sys

    print("Phase 3: 残留 Repository 违规修复工具\n")

    # 切换到正确的目录
    import os
    if 'quantsys-v2' in os.listdir('.'):
        os.chdir('quantsys-v2')
        print("📁 切换到 quantsys-v2 目录\n")

    # 检查接口定义
    missing = analyze_missing_interfaces()

    if missing:
        print(f"\n需要先添加缺失的接口定义: {', '.join(missing)}")
        print("请确认是否继续修复导入路径？(y/n)")
        # 自动继续，不等待输入
        print("自动继续...\n")

    # 修复文件
    print("\n开始修复导入路径...\n")

    fixed = 0
    for file_path, repo_module, interface_name in FILES_TO_FIX:
        if fix_file(file_path, repo_module, interface_name, dry_run=False):
            fixed += 1

    print(f"\n{'='*80}")
    print(f"修复完成: {fixed}/{len(FILES_TO_FIX)} 个文件")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
