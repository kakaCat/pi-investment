#!/usr/bin/env python3
"""pre-commit hook - 防止提交违规代码

安装:
    cp scripts/refactor/pre-commit-hook.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

或使用 pre-commit 框架:
    pip install pre-commit
    pre-commit install
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# 禁止的模式
FORBIDDEN_PATTERNS = [
    (r'sys\.path\.insert\(', "不允许使用 sys.path.insert，请使用 pip install -e ."),
    (r'^\s*print\s*\(', "不允许使用 print() 调试，请使用 logger.info()"),
    (r'^import\s+(akshare|tushare|yfinance)', "不允许直接导入数据源，请使用 DataProviderManager"),
    (r'^from\s+(akshare|tushare|yfinance)', "不允许直接导入数据源，请使用 DataProviderManager"),
]

# 允许的目录
ALLOWED_DIRS = [
    'tests/',
    'adapters/outbound/datasources/',
]


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """检查单个文件
    
    Returns:
        List of (line_number, pattern_description, line_content)
    """
    violations = []
    
    # 检查是否在允许目录
    rel_path = str(file_path)
    if any(rel_path.startswith(allowed) for allowed in ALLOWED_DIRS):
        return violations
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return violations
    
    for i, line in enumerate(lines, start=1):
        # 跳过注释行
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        
        # 检查每个禁止模式
        for pattern, description in FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                violations.append((i, description, line.strip()))
    
    return violations


def main():
    """主函数"""
    # 获取所有暂存的 Python 文件
    import subprocess
    
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=True
        )
        staged_files = result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        print("❌ 无法获取暂存文件列表", file=sys.stderr)
        sys.exit(1)
    
    # 过滤 Python 文件
    py_files = [Path(f) for f in staged_files if f.endswith('.py') and Path(f).exists()]
    
    if not py_files:
        sys.exit(0)
    
    # 检查每个文件
    all_violations = {}
    for py_file in py_files:
        violations = check_file(py_file)
        if violations:
            all_violations[py_file] = violations
    
    # 如果有违规，阻止提交
    if all_violations:
        print("❌ 代码规范检查失败！\n", file=sys.stderr)
        
        for file_path, violations in all_violations.items():
            print(f"📁 {file_path}:", file=sys.stderr)
            for line_num, description, line_content in violations:
                print(f"  行 {line_num}: {description}", file=sys.stderr)
                print(f"    {line_content}", file=sys.stderr)
            print("", file=sys.stderr)
        
        print("💡 修复建议:", file=sys.stderr)
        print("  - 移除 sys.path.insert: python scripts/refactor/remove_sys_path_hacks.py --fix", file=sys.stderr)
        print("  - 替换 print() 为 logger: from infrastructure.logging import get_logger", file=sys.stderr)
        print("  - 使用数据访问层: from adapters.outbound.datasources.manager import get_data_provider_manager", file=sys.stderr)
        print("", file=sys.stderr)
        print("要跳过此检查（不推荐）: git commit --no-verify", file=sys.stderr)
        
        sys.exit(1)
    
    print("✅ 代码规范检查通过")
    sys.exit(0)


if __name__ == '__main__':
    main()
