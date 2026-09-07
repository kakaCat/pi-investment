#!/usr/bin/env python3
"""
异常类迁移脚本

自动将旧的异常类名替换为新的统一异常体系中的类名
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# 异常类映射表
EXCEPTION_MAPPING = {
    # 旧类名 -> (新类名, 新模块路径)
    "InvalidSymbolException": ("ValidationError", "domain.exceptions"),
    "StockNotFoundException": ("SymbolNotFoundError", "domain.exceptions"),
    "DataProviderUnavailableException": ("DataSourceUnavailableError", "domain.exceptions"),
    "InsufficientDataException": ("DataQualityError", "domain.exceptions"),
    "DatabaseException": ("DatabaseError", "domain.exceptions"),
    "InvalidOrderException": ("InvalidOrderError", "domain.exceptions"),
    "InsufficientFundsException": ("InsufficientFundsError", "domain.exceptions"),
    "InsufficientSharesException": ("InsufficientSharesError", "domain.exceptions"),
    "MarketClosedException": ("MarketClosedError", "domain.exceptions"),
    "StrategyNotFoundException": ("StrategyNotFoundError", "domain.exceptions"),
    "BacktestException": ("BacktestError", "domain.exceptions"),
    "SignalGenerationException": ("SignalGenerationError", "domain.exceptions"),
    "ConfigurationException": ("ConfigurationError", "domain.exceptions"),
    "ExternalServiceException": ("ExternalServiceError", "domain.exceptions"),
}


def find_test_files_with_old_exceptions(base_dir: Path) -> List[Path]:
    """查找使用旧异常类的测试文件"""
    test_files = []

    for test_file in base_dir.rglob("test_*.py"):
        try:
            content = test_file.read_text(encoding='utf-8')

            # 检查是否包含旧异常类
            for old_name in EXCEPTION_MAPPING.keys():
                if old_name in content:
                    test_files.append(test_file)
                    break

        except Exception as e:
            print(f"⚠️  无法读取 {test_file}: {e}")

    return test_files


def migrate_file(file_path: Path, dry_run: bool = True) -> Tuple[bool, List[str]]:
    """迁移单个文件"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = []

        # 1. 替换 import 语句
        for old_name, (new_name, _) in EXCEPTION_MAPPING.items():
            # 匹配 from xxx import ..., OldException, ...
            pattern = rf'\bfrom\s+[\w.]+\s+import\s+([^;\n]*\b{old_name}\b[^;\n]*)'

            def replace_import(match):
                import_list = match.group(1)
                # 替换异常类名
                new_import_list = import_list.replace(old_name, new_name)
                changes.append(f"  Import: {old_name} → {new_name}")
                return f"from domain.exceptions import {new_import_list}"

            content = re.sub(pattern, replace_import, content)

        # 2. 替换异常类使用（raise 语句、except 子句）
        for old_name, (new_name, _) in EXCEPTION_MAPPING.items():
            # 匹配 raise OldException(...) 或 except OldException
            pattern = rf'\b{old_name}\b'
            if re.search(pattern, content):
                content = re.sub(pattern, new_name, content)
                if f"  Import: {old_name}" not in str(changes):
                    changes.append(f"  Usage: {old_name} → {new_name}")

        # 3. 检查是否有变更
        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding='utf-8')
            return True, changes
        else:
            return False, []

    except Exception as e:
        print(f"❌ 迁移 {file_path} 失败: {e}")
        return False, []


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="迁移异常类到新的统一体系")
    parser.add_argument("--apply", action="store_true", help="实际执行迁移（默认为 dry-run）")
    parser.add_argument("--base-dir", type=str, default="tests", help="基础目录（默认 tests）")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    dry_run = not args.apply

    print(f"{'🔍 Dry-run 模式' if dry_run else '✏️  执行迁移'}")
    print(f"📂 扫描目录: {base_dir.absolute()}\n")

    # 查找需要迁移的文件
    files_to_migrate = find_test_files_with_old_exceptions(base_dir)

    if not files_to_migrate:
        print("✅ 没有发现需要迁移的文件")
        return

    print(f"📋 发现 {len(files_to_migrate)} 个文件需要迁移:\n")

    # 迁移文件
    migrated_count = 0
    for file_path in files_to_migrate:
        migrated, changes = migrate_file(file_path, dry_run=dry_run)

        if migrated:
            migrated_count += 1
            status = "🔄" if dry_run else "✅"
            print(f"{status} {file_path.relative_to(base_dir)}")
            for change in changes:
                print(change)
            print()

    print(f"\n{'📊 预计' if dry_run else '✅'} 迁移 {migrated_count}/{len(files_to_migrate)} 个文件")

    if dry_run:
        print("\n💡 使用 --apply 参数执行实际迁移")


if __name__ == "__main__":
    main()
