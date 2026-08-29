#!/usr/bin/env python3
"""移除 sys.path.insert hack

Usage:
    # 预览模式 (不修改文件)
    python scripts/refactor/remove_sys_path_hacks.py
    
    # 实际修改
    python scripts/refactor/remove_sys_path_hacks.py --fix
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

def find_sys_path_hacks(file_path: Path) -> List[Tuple[int, str]]:
    """查找文件中的 sys.path.insert 行
    
    Returns:
        List of (line_number, line_content)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    hacks = []
    for i, line in enumerate(lines, start=1):
        if re.search(r'sys\.path\.insert\(', line):
            hacks.append((i, line.rstrip()))
    
    return hacks

def remove_sys_path_hacks(file_path: Path, dry_run: bool = True) -> int:
    """移除文件中的 sys.path.insert 行
    
    Returns:
        Number of lines removed
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找并标记要删除的行
    new_lines = []
    removed_count = 0
    
    for i, line in enumerate(lines):
        # 检查是否是 sys.path.insert
        if re.search(r'sys\.path\.insert\(', line):
            removed_count += 1
            # 保留注释说明
            new_lines.append(f"# REMOVED: {line.rstrip()}\n")
            continue
        
        # 检查是否是相关的 import sys (如果紧挨着 sys.path)
        if line.strip() == 'import sys' and i + 1 < len(lines):
            next_line = lines[i + 1]
            if re.search(r'sys\.path\.insert\(', next_line):
                # 如果下一行是 sys.path.insert，保留 import sys
                # (可能文件其他地方还用到 sys)
                pass
        
        new_lines.append(line)
    
    if not dry_run and removed_count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    
    return removed_count

def scan_and_remove(root_dir: Path, fix: bool = False):
    """扫描并移除所有 sys.path.insert"""
    exclude_dirs = {'venv', '__pycache__', '.git', 'node_modules'}
    
    total_files = 0
    total_removed = 0
    
    print(f"{'=' * 60}")
    print(f"{'FIXING FILES' if fix else 'DRY RUN - No files will be modified'}")
    print(f"{'=' * 60}\n")
    
    for py_file in root_dir.rglob('*.py'):
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        
        hacks = find_sys_path_hacks(py_file)
        if not hacks:
            continue
        
        total_files += 1
        rel_path = py_file.relative_to(root_dir)
        
        print(f"\n📁 {rel_path}")
        print(f"   Found {len(hacks)} sys.path.insert lines:")
        
        for line_num, line_content in hacks:
            print(f"   Line {line_num}: {line_content}")
        
        if fix:
            removed = remove_sys_path_hacks(py_file, dry_run=False)
            total_removed += removed
            print(f"   ✅ Removed {removed} lines")
        else:
            print(f"   (Would remove {len(hacks)} lines in --fix mode)")
    
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Files affected: {total_files}")
    print(f"  Lines {'removed' if fix else 'to remove'}: {total_removed or sum(len(find_sys_path_hacks(f)) for f in root_dir.rglob('*.py') if not any(p in exclude_dirs for p in f.parts))}")
    print(f"{'=' * 60}\n")
    
    if not fix:
        print("ℹ️  Run with --fix to actually modify files")
    else:
        print("✅ Files modified. Remember to:")
        print("   1. Install the package: pip install -e .")
        print("   2. Update imports to use absolute imports")
        print("   3. Run tests: pytest")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='移除 sys.path.insert hack',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes
  python scripts/refactor/remove_sys_path_hacks.py
  
  # Apply changes
  python scripts/refactor/remove_sys_path_hacks.py --fix
  
  # After running, you should:
  1. pip install -e .
  2. Update imports to absolute imports
  3. pytest
        """
    )
    parser.add_argument('--fix', action='store_true',
                        help='Actually modify files (default: dry run)')
    parser.add_argument('--root', type=Path, default=Path('.'),
                        help='Project root directory')
    
    args = parser.parse_args()
    
    if not args.root.is_dir():
        print(f"Error: {args.root} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    scan_and_remove(args.root, fix=args.fix)

if __name__ == '__main__':
    main()
