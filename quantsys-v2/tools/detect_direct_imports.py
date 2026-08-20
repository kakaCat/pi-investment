"""P1-2: Direct akshare/tushare import detection and migration tool.

This tool helps identify and fix violations of the data access architecture rule:
"NEVER directly import external data libraries (akshare, tushare, etc.)"

Usage:
    python tools/detect_direct_imports.py              # Scan and report
    python tools/detect_direct_imports.py --fix FILE   # Auto-fix a file
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict


# Patterns to detect
FORBIDDEN_IMPORTS = [
    r'^\s*import\s+akshare',
    r'^\s*from\s+akshare',
    r'^\s*import\s+tushare',
    r'^\s*from\s+tushare',
]

# Exceptions (files that are allowed to import directly)
ALLOWED_FILES = {
    # Provider adapters (legitimate use - they wrap the libraries)
    'adapters/outbound/datasources/providers/*/akshare.py',
    'adapters/outbound/datasources/providers/*/tushare.py',
    'adapters/outbound/datasources/providers/quantlib/akshare_adapter.py',
    'domain/quantlib/adapters/akshare_adapter.py',

    # Legacy archived scripts (not in production)
    'archived_scripts/*',

    # Tests (may need direct import for mocking)
    'tests/*',
}


def is_allowed(file_path: str) -> bool:
    """Check if a file is allowed to have direct imports."""
    for pattern in ALLOWED_FILES:
        # Convert glob pattern to regex
        regex = pattern.replace('*', '.*').replace('/', r'\/')
        if re.match(regex, file_path):
            return True
    return False


def scan_file(file_path: Path) -> List[Tuple[int, str]]:
    """Scan a file for forbidden imports.

    Returns:
        List of (line_number, line_content) tuples
    """
    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                for pattern in FORBIDDEN_IMPORTS:
                    if re.match(pattern, line):
                        violations.append((line_num, line.rstrip()))
                        break
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return violations


def scan_project(root_dir: Path) -> Dict[str, List[Tuple[int, str]]]:
    """Scan entire project for violations.

    Returns:
        Dict mapping file paths to list of violations
    """
    violations_by_file = {}

    for py_file in root_dir.rglob("*.py"):
        # Skip __pycache__ and virtual environments
        if '__pycache__' in str(py_file) or 'venv' in str(py_file):
            continue

        relative_path = py_file.relative_to(root_dir)

        violations = scan_file(py_file)
        if violations:
            violations_by_file[str(relative_path)] = violations

    return violations_by_file


def categorize_violations(violations: Dict[str, List[Tuple[int, str]]]) -> Dict[str, List[str]]:
    """Categorize violations by directory for prioritization."""
    categories = defaultdict(list)

    for file_path in violations.keys():
        if is_allowed(file_path):
            categories['allowed'].append(file_path)
        elif file_path.startswith('adapters/'):
            categories['adapters'].append(file_path)
        elif file_path.startswith('application/services/'):
            categories['services'].append(file_path)
        elif file_path.startswith('domain/'):
            categories['domain'].append(file_path)
        elif file_path.startswith('infrastructure/'):
            categories['infrastructure'].append(file_path)
        else:
            categories['other'].append(file_path)

    return categories


def generate_report(violations: Dict[str, List[Tuple[int, str]]]) -> str:
    """Generate a human-readable report."""
    categories = categorize_violations(violations)

    report = []
    report.append("=" * 80)
    report.append("P1-2: Direct akshare/tushare Import Violations")
    report.append("=" * 80)
    report.append("")

    # Summary
    total = len(violations)
    allowed = len(categories['allowed'])
    actual_violations = total - allowed

    report.append(f"Total files scanned: {total}")
    report.append(f"Files with violations: {actual_violations}")
    report.append(f"Allowed files (legitimate use): {allowed}")
    report.append("")

    # By category
    report.append("Violations by category:")
    report.append("-" * 80)

    priority_order = ['services', 'adapters', 'domain', 'infrastructure', 'other']
    for category in priority_order:
        files = categories.get(category, [])
        if files:
            report.append(f"\n{category.upper()} ({len(files)} files):")
            for file_path in sorted(files):
                report.append(f"  - {file_path}")
                for line_num, line in violations[file_path][:3]:  # Show first 3
                    report.append(f"      L{line_num}: {line}")
                if len(violations[file_path]) > 3:
                    report.append(f"      ... and {len(violations[file_path]) - 3} more")

    # Allowed files
    if categories['allowed']:
        report.append(f"\nALLOWED ({len(categories['allowed'])} files):")
        for file_path in sorted(categories['allowed']):
            report.append(f"  - {file_path} (legitimate adapter)")

    report.append("")
    report.append("=" * 80)
    report.append("Recommended actions:")
    report.append("-" * 80)
    report.append("1. SERVICES: Migrate to DataProviderManager (highest priority)")
    report.append("2. ADAPTERS: Review if they should be using DataProviderManager")
    report.append("3. DOMAIN: Should NOT import external libs - use adapters")
    report.append("4. Add pre-commit hook to prevent new violations")
    report.append("=" * 80)

    return "\n".join(report)


def suggest_fix(file_path: str, line: str) -> str:
    """Suggest how to fix a violation.

    Returns:
        Suggestion text
    """
    suggestions = []

    if 'import akshare as ak' in line:
        suggestions.append("Replace with:")
        suggestions.append("  from adapters.outbound.datasources.data_provider_manager import DataProviderManager")
        suggestions.append("  provider = DataProviderManager()")
        suggestions.append("  data = provider.get_stock_list()  # Example")

    elif 'from akshare import' in line:
        func = line.split('import')[1].strip()
        suggestions.append(f"Replace 'from akshare import {func}' with:")
        suggestions.append("  from adapters.outbound.datasources.data_provider_manager import DataProviderManager")
        suggestions.append("  provider = DataProviderManager()")
        suggestions.append(f"  # Use provider methods instead of ak.{func}()")

    elif 'import tushare' in line:
        suggestions.append("Replace with:")
        suggestions.append("  from adapters.outbound.datasources.data_provider_manager import DataProviderManager")
        suggestions.append("  # Tushare provider should be integrated into DataProviderManager")

    return "\n".join(suggestions)


# Example migration patterns
MIGRATION_EXAMPLES = """
MIGRATION EXAMPLES
==================

Example 1: Stock list fetching
-------------------------------
BEFORE:
    import akshare as ak

    def get_stock_list():
        df = ak.stock_zh_a_spot_em()
        return df

AFTER:
    from adapters.outbound.datasources.data_provider_manager import DataProviderManager

    def get_stock_list():
        provider = DataProviderManager()
        df = provider.get_stock_list()
        return df

Example 2: K-line data
----------------------
BEFORE:
    import akshare as ak

    def get_klines(symbol, start_date, end_date):
        df = ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, end_date=end_date)
        return df

AFTER:
    from adapters.outbound.datasources.data_provider_manager import DataProviderManager

    def get_klines(symbol, start_date, end_date):
        provider = DataProviderManager()
        # Provider has fallback chain: database → baostock → tencent → akshare
        df = provider.get_klines(symbol, start_date, end_date)
        return df

Example 3: Financial data
--------------------------
BEFORE:
    import akshare as ak

    def get_financial_data(symbol):
        df = ak.stock_financial_analysis_indicator(symbol=symbol)
        return df

AFTER:
    from adapters.outbound.datasources.data_provider_manager import DataProviderManager

    def get_financial_data(symbol):
        provider = DataProviderManager()
        df = provider.get_financial_indicators(symbol)
        return df

Benefits of using DataProviderManager:
---------------------------------------
✅ Automatic fallback chain (database → baostock → tencent → akshare)
✅ Unified error handling (network timeout, IP ban, rate limit)
✅ Centralized configuration (can switch providers globally)
✅ Built-in caching and circuit breaker
✅ Easier to mock for testing
"""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect direct akshare/tushare imports")
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Path to scan (default: current directory)'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate detailed report'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Show migration examples'
    )

    args = parser.parse_args()

    if args.examples:
        print(MIGRATION_EXAMPLES)
        sys.exit(0)

    # Scan project
    root = Path(args.path)
    if not root.exists():
        print(f"Error: Path {root} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {root}...", file=sys.stderr)
    violations = scan_project(root)

    # Generate report
    report = generate_report(violations)
    print(report)

    # Exit code
    categories = categorize_violations(violations)
    actual_violations = len(violations) - len(categories['allowed'])

    if actual_violations > 0:
        print(f"\n⚠️  Found {actual_violations} violations", file=sys.stderr)
        print("Run with --examples to see migration patterns", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n✅ No violations found", file=sys.stderr)
        sys.exit(0)
