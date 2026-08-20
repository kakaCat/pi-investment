"""P1-4: Unified logging system migration tool.

Detects and reports inconsistent logging usage across the codebase:
- Standard library logging (213 files)
- structlog (239 files)
- print() statements (6,473 occurrences)

Usage:
    python tools/detect_logging_issues.py              # Scan and report
    python tools/detect_logging_issues.py --check FILE # Check specific file
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set
from collections import defaultdict


class LoggingAnalyzer:
    """Analyze logging usage in Python files."""

    def __init__(self):
        self.standard_logging_pattern = re.compile(r'^\s*import logging|^\s*from logging')
        self.structlog_pattern = re.compile(r'^\s*import structlog|^\s*from structlog')
        self.print_pattern = re.compile(r'^\s*print\s*\(')
        self.logger_get_pattern = re.compile(r'logging\.getLogger|structlog\.get_logger')

    def analyze_file(self, file_path: Path) -> Dict[str, any]:
        """Analyze logging usage in a single file."""
        result = {
            'has_standard_logging': False,
            'has_structlog': False,
            'print_count': 0,
            'print_lines': [],
            'logger_type': None,
            'mixed_logging': False,
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                # Check for logging imports
                if self.standard_logging_pattern.search(line):
                    result['has_standard_logging'] = True
                if self.structlog_pattern.search(line):
                    result['has_structlog'] = True

                # Check for print statements
                if self.print_pattern.search(line):
                    # Exclude docstrings and comments
                    stripped = line.strip()
                    if not stripped.startswith('#') and not stripped.startswith('"""'):
                        result['print_count'] += 1
                        result['print_lines'].append((line_num, line.strip()))

                # Determine logger type
                if self.logger_get_pattern.search(line):
                    if 'logging.getLogger' in line:
                        result['logger_type'] = 'standard'
                    elif 'structlog.get_logger' in line:
                        result['logger_type'] = 'structlog'

            # Check for mixed logging
            if result['has_standard_logging'] and result['has_structlog']:
                result['mixed_logging'] = True

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}", file=sys.stderr)

        return result

    def scan_project(self, root_dir: Path) -> Dict[str, Dict]:
        """Scan entire project for logging issues."""
        results = {}

        for py_file in root_dir.rglob("*.py"):
            if '__pycache__' in str(py_file) or 'venv' in str(py_file):
                continue

            relative_path = str(py_file.relative_to(root_dir))
            analysis = self.analyze_file(py_file)

            # Only include files with logging or print statements
            if (analysis['has_standard_logging'] or
                analysis['has_structlog'] or
                analysis['print_count'] > 0):
                results[relative_path] = analysis

        return results


def categorize_files(results: Dict[str, Dict]) -> Dict[str, List[str]]:
    """Categorize files by logging pattern."""
    categories = {
        'standard_only': [],
        'structlog_only': [],
        'mixed_logging': [],
        'print_heavy': [],  # > 10 print statements
        'print_only': [],    # No logger, only print
    }

    for file_path, analysis in results.items():
        if analysis['mixed_logging']:
            categories['mixed_logging'].append(file_path)
        elif analysis['has_structlog']:
            categories['structlog_only'].append(file_path)
        elif analysis['has_standard_logging']:
            categories['standard_only'].append(file_path)

        if analysis['print_count'] > 10:
            categories['print_heavy'].append(file_path)
        elif analysis['print_count'] > 0 and not analysis['has_standard_logging'] and not analysis['has_structlog']:
            categories['print_only'].append(file_path)

    return categories


def generate_report(results: Dict[str, Dict]) -> str:
    """Generate human-readable report."""
    categories = categorize_files(results)

    report = []
    report.append("=" * 80)
    report.append("P1-4: Logging System Inconsistency Report")
    report.append("=" * 80)
    report.append("")

    # Summary statistics
    total_files = len(results)
    total_prints = sum(r['print_count'] for r in results.values())

    standard_count = sum(1 for r in results.values() if r['has_standard_logging'])
    structlog_count = sum(1 for r in results.values() if r['has_structlog'])
    mixed_count = len(categories['mixed_logging'])
    print_only_count = len(categories['print_only'])

    report.append("Summary:")
    report.append("-" * 80)
    report.append(f"Total files analyzed: {total_files}")
    report.append(f"Files using standard logging: {standard_count}")
    report.append(f"Files using structlog: {structlog_count}")
    report.append(f"Files with mixed logging: {mixed_count} ⚠️")
    report.append(f"Files using only print(): {print_only_count} ⚠️")
    report.append(f"Total print() statements: {total_prints} ⚠️")
    report.append("")

    # Category breakdown
    report.append("Issues by category:")
    report.append("-" * 80)

    if categories['mixed_logging']:
        report.append(f"\n🔴 MIXED LOGGING ({len(categories['mixed_logging'])} files):")
        report.append("   These files use both standard logging and structlog")
        for file_path in sorted(categories['mixed_logging'])[:10]:
            report.append(f"   - {file_path}")
        if len(categories['mixed_logging']) > 10:
            report.append(f"   ... and {len(categories['mixed_logging']) - 10} more")

    if categories['print_heavy']:
        report.append(f"\n🟡 PRINT-HEAVY FILES ({len(categories['print_heavy'])} files):")
        report.append("   Files with more than 10 print() statements")
        for file_path in sorted(categories['print_heavy'],
                               key=lambda f: results[f]['print_count'],
                               reverse=True)[:10]:
            count = results[file_path]['print_count']
            report.append(f"   - {file_path} ({count} prints)")
        if len(categories['print_heavy']) > 10:
            report.append(f"   ... and {len(categories['print_heavy']) - 10} more")

    if categories['print_only']:
        report.append(f"\n🟡 PRINT-ONLY FILES ({len(categories['print_only'])} files):")
        report.append("   Files using print() without any logger")
        for file_path in sorted(categories['print_only'])[:10]:
            report.append(f"   - {file_path}")
        if len(categories['print_only']) > 10:
            report.append(f"   ... and {len(categories['print_only']) - 10} more")

    report.append("")
    report.append("=" * 80)
    report.append("Recommendations:")
    report.append("-" * 80)
    report.append("1. Standardize on structlog (already configured in main.py)")
    report.append("2. Replace print() with logger.debug() in production code")
    report.append("3. Add lint rule to catch new print() usage")
    report.append("4. Keep print() only in scripts/ and tools/")
    report.append("=" * 80)

    return "\n".join(report)


MIGRATION_GUIDE = """
# Logging System Migration Guide

## Target: Unified structlog

quantsys-v2 has already configured structlog in infrastructure/logging.py
and main.py. All code should migrate to this system.

## Why structlog?

✅ Structured logging (JSON output for production)
✅ Context binding (trace_id, request_id, etc.)
✅ Better performance than standard logging
✅ Easy filtering and analysis (log aggregation tools love it)
✅ Type-safe with modern Python

## Migration Patterns

### Pattern 1: Standard logging → structlog

BEFORE:
```python
import logging

logger = logging.getLogger(__name__)

def process_data(symbol: str):
    logger.info(f"Processing {symbol}")
    try:
        result = fetch_data(symbol)
        logger.info(f"Success: {symbol}")
        return result
    except Exception as e:
        logger.error(f"Failed {symbol}: {e}")
        raise
```

AFTER:
```python
import structlog

logger = structlog.get_logger(__name__)

def process_data(symbol: str):
    # Bind context once
    log = logger.bind(symbol=symbol)

    log.info("processing_data")
    try:
        result = fetch_data(symbol)
        log.info("processing_success")
        return result
    except Exception as e:
        log.error("processing_failed", error=str(e), error_type=type(e).__name__)
        raise
```

Benefits:
- No string formatting (better performance)
- Structured fields (symbol, error, error_type)
- Easy to query: `jq '.symbol == "600000.SH"' logs.json`

### Pattern 2: print() → logger.debug()

BEFORE:
```python
def calculate_indicator(prices):
    print(f"Calculating for {len(prices)} prices")
    result = compute(prices)
    print(f"Result: {result}")
    return result
```

AFTER:
```python
import structlog

logger = structlog.get_logger(__name__)

def calculate_indicator(prices):
    logger.debug("calculating_indicator", price_count=len(prices))
    result = compute(prices)
    logger.debug("calculation_complete", result=result)
    return result
```

### Pattern 3: Debug print() → Conditional logging

BEFORE:
```python
def complex_calculation(data):
    print("Step 1: preprocessing")
    preprocessed = preprocess(data)
    print(f"Preprocessed: {preprocessed}")

    print("Step 2: computation")
    result = compute(preprocessed)
    print(f"Result: {result}")

    return result
```

AFTER:
```python
import structlog

logger = structlog.get_logger(__name__)

def complex_calculation(data):
    log = logger.bind(operation="complex_calculation")

    log.debug("step_preprocessing")
    preprocessed = preprocess(data)
    log.debug("preprocessing_complete", data_shape=preprocessed.shape)

    log.debug("step_computation")
    result = compute(preprocessed)
    log.debug("computation_complete", result_summary=result[:5])

    return result
```

Control via environment variable:
```bash
# Development: see all debug logs
LOG_LEVEL=DEBUG python main.py

# Production: only info and above
LOG_LEVEL=INFO python main.py
```

### Pattern 4: Exception logging

BEFORE:
```python
try:
    process()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
```

AFTER:
```python
try:
    process()
except Exception as e:
    logger.exception("process_failed", error=str(e))
    # structlog.exception() automatically includes traceback
```

## Keeping print() (Allowed Cases)

Keep print() ONLY in:

1. **CLI scripts** (scripts/, tools/) - User-facing output
   ```python
   # tools/some_script.py
   print("✓ Migration complete")
   print(f"Processed {count} files")
   ```

2. **Interactive tools**
   ```python
   # tools/interactive_debugger.py
   answer = input("Continue? (y/n): ")
   print(f"You chose: {answer}")
   ```

3. **Test output** (when debugging tests)
   ```python
   # tests/test_something.py
   def test_feature():
       result = complex_function()
       print(f"DEBUG: result = {result}")  # Temporary debugging
       assert result == expected
   ```

DO NOT use print() in:
- application/
- adapters/
- domain/
- infrastructure/

## Structured Logging Best Practices

### 1. Bind context early

```python
def handle_request(symbol: str, date: str):
    # Bind context once
    log = logger.bind(symbol=symbol, date=date)

    log.info("request_started")
    # All subsequent logs include symbol and date
    log.debug("fetching_data")
    data = fetch(symbol, date)
    log.info("request_complete", records=len(data))
```

### 2. Use snake_case event names

```python
# Good
logger.info("data_fetch_started")
logger.info("validation_failed")

# Bad
logger.info("Data Fetch Started")
logger.info("ValidationFailed")
```

### 3. Add structured fields, not formatted strings

```python
# Good
logger.info("order_placed", symbol="600000.SH", quantity=100, price=10.5)

# Bad
logger.info(f"Order placed: {symbol}, qty={quantity}, price={price}")
```

### 4. Use appropriate log levels

```python
logger.debug("detailed_calculation_step", intermediate=value)  # Development
logger.info("user_action", action="login", user_id=123)        # Normal operations
logger.warning("rate_limit_approaching", usage=0.8)            # Attention needed
logger.error("api_call_failed", provider="akshare")            # Errors
logger.critical("database_unreachable")                        # System down
```

## Lint Rules

Add to pyproject.toml:

```toml
[tool.ruff]
select = [
    "T20",  # flake8-print (catches print statements)
]

# Allow print() only in specific directories
[tool.ruff.per-file-ignores]
"scripts/*.py" = ["T20"]
"tools/*.py" = ["T20"]
"tests/*.py" = ["T20"]
```

## Pre-commit Hook

```python
# .git/hooks/pre-commit
import re
import sys

forbidden_pattern = r'^\s*print\s*\('
production_dirs = ['application/', 'adapters/', 'domain/', 'infrastructure/']

for file in staged_files:
    if any(file.startswith(d) for d in production_dirs):
        if re.search(forbidden_pattern, file_content):
            print(f"ERROR: print() found in {file}")
            print("Use logger.debug() instead")
            sys.exit(1)
```

## Migration Priority

1. **P0: Mixed logging files** - Confusing and error-prone
2. **P1: Print-heavy production code** - application/, adapters/
3. **P2: Standard logging → structlog** - Gradual migration
4. **P3: Scripts and tools** - Lower priority

Estimated time: 2-3 days for complete migration
"""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect logging inconsistencies")
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Path to scan (default: current directory)'
    )
    parser.add_argument(
        '--guide',
        action='store_true',
        help='Show migration guide'
    )
    parser.add_argument(
        '--check',
        metavar='FILE',
        help='Check specific file'
    )

    args = parser.parse_args()

    if args.guide:
        print(MIGRATION_GUIDE)
        sys.exit(0)

    root = Path(args.path)
    if not root.exists():
        print(f"Error: Path {root} does not exist", file=sys.stderr)
        sys.exit(1)

    if args.check:
        # Check specific file
        file_path = Path(args.check)
        if not file_path.exists():
            print(f"Error: File {file_path} does not exist", file=sys.stderr)
            sys.exit(1)

        analyzer = LoggingAnalyzer()
        result = analyzer.analyze_file(file_path)

        print(f"Analysis of {file_path}:")
        print(f"  Standard logging: {result['has_standard_logging']}")
        print(f"  Structlog: {result['has_structlog']}")
        print(f"  Logger type: {result['logger_type']}")
        print(f"  Print count: {result['print_count']}")
        print(f"  Mixed logging: {result['mixed_logging']}")

        if result['print_lines']:
            print(f"\nPrint statements:")
            for line_num, line in result['print_lines'][:10]:
                print(f"  L{line_num}: {line}")
            if len(result['print_lines']) > 10:
                print(f"  ... and {len(result['print_lines']) - 10} more")

        sys.exit(0)

    # Full project scan
    print(f"Scanning {root}...", file=sys.stderr)
    analyzer = LoggingAnalyzer()
    results = analyzer.scan_project(root)

    report = generate_report(results)
    print(report)

    print("\nTo see migration guide: python tools/detect_logging_issues.py --guide")
    print("To check specific file: python tools/detect_logging_issues.py --check FILE")
