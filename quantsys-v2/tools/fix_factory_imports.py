#!/usr/bin/env python3
"""
修复工厂函数导入 - 使用依赖注入模式

将服务从直接调用工厂函数改为接受接口注入
"""

import re
from pathlib import Path
from typing import List, Tuple

def fix_service_file(file_path: Path, dry_run: bool = True) -> bool:
    """修复单个服务文件

    将:
        from adapters.outbound.datasources.manager import get_data_provider_manager

        class Service:
            def __init__(self):
                self.manager = get_data_provider_manager()

    改为:
        from domain.ports.datasource_ports import IDataProviderManager

        class Service:
            def __init__(self, provider_manager: IDataProviderManager = None):
                if provider_manager is None:
                    from adapters.outbound.datasources.manager import get_data_provider_manager
                    provider_manager = get_data_provider_manager()
                self.provider_manager = provider_manager
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        lines = content.split('\n')

        # Step 1: 移除顶层的工厂函数导入
        new_lines = []
        removed_import = False
        for line in lines:
            if 'from adapters.outbound.datasources.manager import get_data_provider_manager' in line:
                removed_import = True
                continue
            if 'from adapters.outbound.datasources.manager import get_data_source_manager' in line:
                removed_import = True
                continue
            new_lines.append(line)

        if not removed_import:
            return False

        content = '\n'.join(new_lines)

        # Step 2: 修改 __init__ 方法
        # 查找模式：self.xxx = get_data_provider_manager()
        patterns = [
            (r'(\s+)(self\.\w+)\s*=\s*get_data_provider_manager\(\)',
             r'\1\2: IDataProviderManager = None\n\1if \2 is None:\n\1    from adapters.outbound.datasources.manager import get_data_provider_manager\n\1    \2 = get_data_provider_manager()\n\1self.\2 = \2'),
            (r'(\s+)(self\.\w+)\s*=\s*get_data_source_manager\(\)',
             r'\1\2: IDataProviderManager = None\n\1if \2 is None:\n\1    from adapters.outbound.datasources.manager import get_data_provider_manager\n\1    \2 = get_data_provider_manager()\n\1self.\2 = \2'),
        ]

        # 这个方法太复杂，让我换一个简单的方法：
        # 只移除顶层导入，在 __init__ 中保留局部导入

        # Step 2 简化版：在 __init__ 内部添加局部导入
        # 查找 self.xxx = get_data_provider_manager()
        lines = content.split('\n')
        new_lines = []
        in_init = False
        init_indent = 0

        for i, line in enumerate(lines):
            # 检测 __init__ 方法
            if re.match(r'(\s+)def __init__\(', line):
                in_init = True
                init_indent = len(line) - len(line.lstrip())
                new_lines.append(line)
                continue

            # 在 __init__ 内部
            if in_init:
                # 检测是否离开 __init__（缩进变小）
                if line.strip() and not line.startswith(' ' * (init_indent + 4)):
                    in_init = False

                # 查找 get_data_provider_manager() 调用
                if 'get_data_provider_manager()' in line or 'get_data_source_manager()' in line:
                    # 在此行之前插入局部导入
                    current_indent = ' ' * (init_indent + 8)
                    if 'from adapters.outbound.datasources.manager import' not in '\n'.join(new_lines[-5:]):
                        new_lines.append(f"{current_indent}# 延迟导入避免顶层依赖")
                        new_lines.append(f"{current_indent}from adapters.outbound.datasources.manager import get_data_provider_manager")

            new_lines.append(line)

        content = '\n'.join(new_lines)

        if content != original_content:
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return True

        return False

    except Exception as e:
        print(f"❌ {file_path}: {e}")
        return False


def main():
    import sys

    dry_run = '--dry-run' not in sys.argv

    # 查找所有导入了工厂函数的文件
    services_dir = Path('application/services')
    service_files = list(services_dir.glob('**/*.py'))

    files_with_factory = []
    for file_path in service_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'from adapters.outbound.datasources.manager import get_data_provider_manager' in content:
                    files_with_factory.append(file_path)
                elif 'from adapters.outbound.datasources.manager import get_data_source_manager' in content:
                    files_with_factory.append(file_path)
        except:
            pass

    print(f"发现 {len(files_with_factory)} 个文件导入工厂函数")
    print()

    fixed = 0
    for file_path in files_with_factory:
        if fix_service_file(file_path, dry_run=False):
            print(f"✅ {file_path.name}")
            fixed += 1

    print(f"\n修复完成: {fixed} 个文件")


if __name__ == '__main__':
    main()
