"""P1-3: sys.path modification detection and cleanup tool.

This tool helps identify and remove unnecessary sys.path.insert() calls
that make imports fragile and testing difficult.

Usage:
    python tools/detect_syspath_modifications.py              # Scan and report
    python tools/detect_syspath_modifications.py --fix FILE   # Remove from file
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict


def scan_file(file_path: Path) -> List[Tuple[int, str]]:
    """Scan a file for sys.path modifications.

    Returns:
        List of (line_number, line_content) tuples
    """
    modifications = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                if 'sys.path.insert' in line or 'sys.path.append' in line:
                    modifications.append((line_num, line.rstrip()))
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return modifications


def scan_project(root_dir: Path) -> Dict[str, List[Tuple[int, str]]]:
    """Scan entire project for sys.path modifications."""
    modifications_by_file = {}

    for py_file in root_dir.rglob("*.py"):
        if '__pycache__' in str(py_file) or 'venv' in str(py_file):
            continue

        relative_path = py_file.relative_to(root_dir)
        modifications = scan_file(py_file)

        if modifications:
            modifications_by_file[str(relative_path)] = modifications

    return modifications_by_file


def categorize_files(modifications: Dict[str, List[Tuple[int, str]]]) -> Dict[str, List[str]]:
    """Categorize files by type."""
    categories = defaultdict(list)

    for file_path in modifications.keys():
        if file_path.startswith('tests/'):
            categories['tests'].append(file_path)
        elif file_path.startswith('scripts/'):
            categories['scripts'].append(file_path)
        elif file_path.startswith('archived_scripts/'):
            categories['archived'].append(file_path)
        elif file_path.startswith('tools/'):
            categories['tools'].append(file_path)
        elif file_path.startswith('adapters/'):
            categories['adapters'].append(file_path)
        elif file_path.startswith('application/'):
            categories['application'].append(file_path)
        elif file_path.startswith('domain/'):
            categories['domain'].append(file_path)
        elif file_path.startswith('infrastructure/'):
            categories['infrastructure'].append(file_path)
        else:
            categories['other'].append(file_path)

    return categories


def generate_report(modifications: Dict[str, List[Tuple[int, str]]]) -> str:
    """Generate human-readable report."""
    categories = categorize_files(modifications)

    report = []
    report.append("=" * 80)
    report.append("P1-3: sys.path Modification Analysis")
    report.append("=" * 80)
    report.append("")
    report.append(f"Total files with sys.path modifications: {len(modifications)}")
    report.append("")

    report.append("Distribution by category:")
    report.append("-" * 80)
    for category, files in sorted(categories.items(), key=lambda x: -len(x[1])):
        report.append(f"  {category.upper()}: {len(files)} files")

    report.append("")
    report.append("Common patterns:")
    report.append("-" * 80)

    # Analyze common patterns
    patterns = defaultdict(int)
    for file_modifications in modifications.values():
        for _, line in file_modifications:
            if 'parent' in line and 'parent' in line:
                patterns['pathlib parent traversal'] += 1
            elif '__file__' in line:
                patterns['__file__ based'] += 1
            elif 'os.path' in line:
                patterns['os.path based'] += 1
            else:
                patterns['other'] += 1

    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
        report.append(f"  {pattern}: {count} occurrences")

    report.append("")
    report.append("=" * 80)
    report.append("Recommendations:")
    report.append("-" * 80)
    report.append("1. Remove sys.path modifications from production code")
    report.append("2. Use proper package structure (pyproject.toml or setup.py)")
    report.append("3. Set PYTHONPATH environment variable if needed")
    report.append("4. Keep main.py's sys.path setup (already handles project root)")
    report.append("=" * 80)

    return "\n".join(report)


SOLUTION_DOC = """
# Removing sys.path Modifications

## Problem

Large number of files contain:
```python
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
```

This causes:
- Import order dependencies (which file modifies path first?)
- Testing issues (pytest uses different import mechanism)
- Code smell (proper Python projects don't need this)

## Solution 1: Proper Package Structure (Recommended)

### Create pyproject.toml

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "quantsys-v2"
version = "2.0.0"
requires-python = ">=3.9"

[tool.setuptools.packages.find]
where = ["."]
include = ["application*", "adapters*", "domain*", "infrastructure*"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

### Install in editable mode

```bash
pip install -e .
```

Now all imports work without sys.path modifications!

## Solution 2: PYTHONPATH Environment Variable

### Development

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/quantsys-v2"
```

Or in .env file:
```
PYTHONPATH=/path/to/quantsys-v2
```

### Production (systemd service)

```ini
[Service]
Environment="PYTHONPATH=/opt/quantsys-v2"
ExecStart=/usr/bin/python main.py
```

## Solution 3: Keep One Central Path Setup

### main.py handles it (already done!)

```python
# main.py
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now all other files can use absolute imports without sys.path
```

All other files can then use:
```python
from application.services.data_service import DataService
from domain.models.stock import Stock
```

No sys.path needed!

## Migration Steps

### Step 1: Identify files with sys.path modifications

```bash
python tools/detect_syspath_modifications.py > syspath_report.txt
```

### Step 2: Remove sys.path lines

```python
# REMOVE these lines:
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# KEEP only the actual imports:
from application.services.data_service import DataService
```

### Step 3: Test imports still work

```bash
# From project root
python -m pytest tests/

# Run specific file
python application/services/data_service.py

# If imports fail, you may need pyproject.toml (Solution 1)
```

### Step 4: Update pytest configuration

```ini
# pytest.ini
[pytest]
pythonpath = .
testpaths = tests
python_files = test_*.py
```

## Files to Keep sys.path

Only these files should modify sys.path:

1. **main.py** - Entry point, sets up project root
2. **Standalone scripts** in scripts/ or tools/ - May need it
3. **Tests with special requirements** - Rare cases

All application/, adapters/, domain/, infrastructure/ files should NOT modify sys.path.

## Verification

After cleanup, run:
```bash
# Should find only a few files (main.py, scripts/)
python tools/detect_syspath_modifications.py

# All tests should still pass
pytest

# Application should still start
python main.py
```
"""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect sys.path modifications")
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Path to scan (default: current directory)'
    )
    parser.add_argument(
        '--solution',
        action='store_true',
        help='Show solution documentation'
    )

    args = parser.parse_args()

    if args.solution:
        print(SOLUTION_DOC)
        sys.exit(0)

    # Scan project
    root = Path(args.path)
    if not root.exists():
        print(f"Error: Path {root} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {root}...", file=sys.stderr)
    modifications = scan_project(root)

    # Generate report
    report = generate_report(modifications)
    print(report)

    # Show sample files
    print("\nSample files (first 10):")
    print("-" * 80)
    for i, (file_path, mods) in enumerate(list(modifications.items())[:10]):
        print(f"\n{i+1}. {file_path}")
        for line_num, line in mods[:2]:  # Show first 2 lines
            print(f"   L{line_num}: {line[:70]}")

    if len(modifications) > 10:
        print(f"\n... and {len(modifications) - 10} more files")

    print("\n" + "=" * 80)
    print("To see full solution: python tools/detect_syspath_modifications.py --solution")
    print("=" * 80)
