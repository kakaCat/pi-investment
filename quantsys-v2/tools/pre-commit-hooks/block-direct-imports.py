#!/usr/bin/env python3
"""Pre-commit hook: Block direct akshare/tushare imports.

Installation:
    cp tools/pre-commit-hooks/block-direct-imports.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Or add to .pre-commit-config.yaml for pre-commit framework.
"""
import sys
import re
from pathlib import Path

# Patterns to detect
FORBIDDEN_PATTERNS = [
    r'^\s*import\s+akshare',
    r'^\s*from\s+akshare',
    r'^\s*import\s+tushare',
    r'^\s*from\s+tushare',
]

# Files that are allowed (provider adapters)
ALLOWED_PATHS = [
    'adapters/outbound/datasources/providers/',
    'domain/quantlib/adapters/',
    'archived_scripts/',
    'tests/',
    'tools/detect_direct_imports.py',  # This file contains examples
]


def is_allowed(file_path: str) -> bool:
    """Check if file is allowed to have direct imports."""
    for allowed in ALLOWED_PATHS:
        if allowed in file_path:
            return True
    return False


def check_file(file_path: Path) -> list:
    """Check a file for forbidden imports.

    Returns:
        List of (line_number, line_content) violations
    """
    if not file_path.exists():
        return []

    if is_allowed(str(file_path)):
        return []

    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                for pattern in FORBIDDEN_PATTERNS:
                    if re.match(pattern, line):
                        violations.append((line_num, line.rstrip()))
                        break
    except Exception:
        pass  # Skip files that can't be read

    return violations


def main():
    """Check staged files for violations."""
    import subprocess

    # Get staged Python files
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return 0  # Not a git repo, skip check

    staged_files = [
        Path(f) for f in result.stdout.strip().split('\n')
        if f.endswith('.py')
    ]

    if not staged_files:
        return 0  # No Python files staged

    # Check each file
    violations_found = False

    for file_path in staged_files:
        violations = check_file(file_path)

        if violations:
            violations_found = True
            print(f"\n❌ BLOCKED: {file_path}")
            print("   Direct akshare/tushare imports are not allowed")
            print()

            for line_num, line in violations:
                print(f"   Line {line_num}: {line}")

            print()
            print("   ℹ️  Use DataProviderManager instead:")
            print("   from adapters.outbound.datasources.data_provider_manager import DataProviderManager")
            print("   provider = DataProviderManager()")
            print()

    if violations_found:
        print("=" * 80)
        print("⚠️  Commit blocked due to direct akshare/tushare imports")
        print("=" * 80)
        print()
        print("Why this is blocked:")
        print("  - Violates architecture rule: 'NEVER directly import external data libraries'")
        print("  - Makes data source switching difficult")
        print("  - Bypasses unified fallback chain and error handling")
        print()
        print("To fix:")
        print("  1. Use DataProviderManager for data fetching")
        print("  2. See examples: python tools/detect_direct_imports.py --examples")
        print("  3. If this is a legitimate provider adapter, move to:")
        print("     adapters/outbound/datasources/providers/<provider_name>/")
        print()
        print("To bypass this check (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        print("=" * 80)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
