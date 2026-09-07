#!/usr/bin/env python3
"""Fix 'from __future__ import annotations' position in Python files.

This script moves the future import to line 1 as required by Python syntax.
"""
import re
import sys
from pathlib import Path


def fix_future_import(filepath: Path) -> bool:
    """Fix future import position in a file.

    Returns:
        True if file was modified, False otherwise
    """
    content = filepath.read_text()
    lines = content.splitlines(keepends=True)

    # Find the future import line
    future_line_idx = None
    for i, line in enumerate(lines):
        if re.match(r'^from __future__ import annotations\s*$', line.strip()):
            future_line_idx = i
            break

    if future_line_idx is None:
        return False  # No future import found

    if future_line_idx == 0:
        return False  # Already at line 1

    # Extract the future import line
    future_line = lines[future_line_idx]

    # Remove it from its current position
    lines.pop(future_line_idx)

    # Insert at the beginning
    lines.insert(0, future_line)

    # Write back
    filepath.write_text(''.join(lines))
    print(f"Fixed: {filepath}")
    return True


def main():
    root = Path(__file__).parent.parent

    # Find all Python files with misplaced future imports
    python_files = root.rglob("*.py")

    fixed_count = 0
    for filepath in python_files:
        try:
            if fix_future_import(filepath):
                fixed_count += 1
        except Exception as e:
            print(f"Error processing {filepath}: {e}", file=sys.stderr)

    print(f"\nFixed {fixed_count} files")


if __name__ == '__main__':
    main()
