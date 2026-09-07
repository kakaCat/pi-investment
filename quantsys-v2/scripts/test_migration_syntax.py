#!/usr/bin/env python3
"""P1-2 迁移语法检查"""

import ast
import sys
from pathlib import Path

# 已迁移的文件列表
MIGRATED_FILES = [
    "application/services/financial_analysis_service.py",
    "application/services/hk_market_data_service.py",
    "application/services/market_data_service.py",
    "application/services/stock_data_service.py",
    "application/services/strategy_code_service.py",
    "application/services/valuation_data_service.py",
    "infrastructure/jobs/index_constituents_update_job.py",
]

def check_syntax(file_path: Path) -> tuple[bool, str]:
    """检查文件语法是否正确"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, "语法正确"
    except SyntaxError as e:
        return False, f"语法错误: {e}"
    except Exception as e:
        return False, f"其他错误: {e}"

def check_no_direct_imports(file_path: Path) -> tuple[bool, list]:
    """检查是否还有直接的 akshare/tushare 导入"""
    direct_imports = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if 'import akshare' in line or 'import tushare' in line:
                    if 'from akshare' not in line and 'from tushare' not in line:
                        if '#' not in line.split('import')[0]:  # 不是注释
                            direct_imports.append((line_num, line.strip()))
        return len(direct_imports) == 0, direct_imports
    except Exception as e:
        return False, [f"错误: {e}"]

def check_provider_manager_usage(file_path: Path) -> tuple[bool, str]:
    """检查是否使用了 provider_manager"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否有 provider_manager 定义（类成员或局部变量）
        has_provider_manager = 'self.provider_manager' in content or 'provider_manager = get_data_provider_manager()' in content

        # 2026-09-05 语义反转：DataProviderManager 无 call_akshare 方法（调用会被
        # try/except 吞成 AttributeError → 静默降级 NaN/stale_cache）。迁移完成态 =
        # 使用 provider_manager.get_*() 且零 call_akshare 残留。
        residual = []
        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):  # 注释不计
                continue
            if '.call_akshare(' in stripped:
                residual.append((line_num, stripped))

        if not has_provider_manager:
            return False, "❌ 未使用 provider_manager"
        elif residual:
            return False, f"❌ 残留 call_akshare 调用 {len(residual)} 处（DataProviderManager 无此方法）: {residual[:3]}"
        else:
            return True, "✅ 已迁移到 provider_manager.get_*()，无 call_akshare 残留"
    except Exception as e:
        return False, f"错误: {e}"

def main():
    print("=" * 70)
    print("P1-2 迁移语法检查")
    print("=" * 70)

    project_root = Path(__file__).parent
    all_passed = True

    for file_rel_path in MIGRATED_FILES:
        file_path = project_root / file_rel_path
        print(f"\n检查: {file_rel_path}")

        # 1. 语法检查
        syntax_ok, syntax_msg = check_syntax(file_path)
        if syntax_ok:
            print(f"  ✅ 语法检查通过")
        else:
            print(f"  ❌ {syntax_msg}")
            all_passed = False
            continue

        # 2. 检查直接导入
        no_direct, imports = check_no_direct_imports(file_path)
        if no_direct:
            print(f"  ✅ 无直接 akshare/tushare 导入")
        else:
            print(f"  ❌ 发现直接导入:")
            for line_num, line in imports:
                print(f"     L{line_num}: {line}")
            all_passed = False

        # 3. 检查 provider_manager 使用
        uses_manager, msg = check_provider_manager_usage(file_path)
        print(f"  {msg}")
        if not uses_manager:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有检查通过！迁移成功！")
        return 0
    else:
        print("⚠️  部分检查失败，请修复上述问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())
