#!/usr/bin/env python3
"""查找直接导入外部数据源库的代码

Usage:
    python scripts/refactor/find_direct_imports.py
    python scripts/refactor/find_direct_imports.py --output direct-imports.json
"""

import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass, asdict

@dataclass
class ImportViolation:
    """导入违规记录"""
    file: str
    line: int
    import_type: str  # "import akshare" or "from akshare import"
    library: str  # akshare/tushare/yfinance
    imported_names: List[str]
    severity: str  # critical/high/medium
    suggestion: str

# 禁止直接导入的库
FORBIDDEN_IMPORTS = {
    'akshare': 'DataProviderManager (adapters/outbound/datasources/manager.py)',
    'tushare': 'DataProviderManager',
    'yfinance': 'DataProviderManager',
    'baostock': 'DataProviderManager',
    'efinance': 'DataProviderManager',
}

# 允许的目录 (数据源适配器层)
ALLOWED_DIRS = {
    'adapters/outbound/datasources',
    'tests',  # 测试可以直接导入 (但应该注释说明)
}

def is_allowed_file(file_path: Path, root: Path) -> bool:
    """检查文件是否允许直接导入"""
    rel_path = str(file_path.relative_to(root))
    return any(rel_path.startswith(allowed) for allowed in ALLOWED_DIRS)

def classify_severity(file_path: str) -> str:
    """根据文件位置判断严重性"""
    if any(x in file_path for x in ['domain/', 'application/services/', 'repositories/']):
        return 'critical'  # 核心层绝对不允许
    elif any(x in file_path for x in ['api/', 'adapters/inbound/']):
        return 'high'  # API 层不应该直接导入
    elif 'scripts/' in file_path:
        return 'medium'  # 脚本层应该避免
    else:
        return 'medium'

def scan_imports(root_dir: Path) -> List[ImportViolation]:
    """扫描所有 Python 文件中的禁止导入"""
    violations = []
    
    exclude_dirs = {'venv', '__pycache__', '.git', 'node_modules', '.pytest_cache'}
    
    for py_file in root_dir.rglob('*.py'):
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        
        # 检查是否在允许目录中
        if is_allowed_file(py_file, root_dir):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Cannot read {py_file}: {e}", file=sys.stderr)
            continue
        
        for i, line in enumerate(lines, start=1):
            line = line.strip()
            
            # 跳过注释行
            if line.startswith('#'):
                continue
            
            # 匹配 import 语句
            for library, suggestion in FORBIDDEN_IMPORTS.items():
                # 匹配 "import akshare" 或 "import akshare as ak"
                match1 = re.match(rf'^import\s+{library}(\s+as\s+\w+)?', line)
                if match1:
                    violations.append(ImportViolation(
                        file=str(py_file.relative_to(root_dir)),
                        line=i,
                        import_type=f"import {library}",
                        library=library,
                        imported_names=[],
                        severity=classify_severity(str(py_file)),
                        suggestion=f"Use {suggestion} instead"
                    ))
                
                # 匹配 "from akshare import xxx"
                match2 = re.match(rf'^from\s+{library}(?:\.\w+)?\s+import\s+(.+)', line)
                if match2:
                    imported = [x.strip() for x in match2.group(1).split(',')]
                    violations.append(ImportViolation(
                        file=str(py_file.relative_to(root_dir)),
                        line=i,
                        import_type=f"from {library} import",
                        library=library,
                        imported_names=imported,
                        severity=classify_severity(str(py_file)),
                        suggestion=f"Use {suggestion}.get_klines(), get_quote(), etc."
                    ))
    
    return violations

def format_report(violations: List[ImportViolation]) -> str:
    """格式化为文本报告"""
    from collections import Counter
    
    output = ["# 直接导入数据源检测报告", ""]
    output.append(f"**总违规数**: {len(violations)}")
    output.append("")
    
    # 按严重性统计
    severity_counts = Counter(v.severity for v in violations)
    output.append("## 按严重性统计")
    output.append("")
    output.append("| 严重性 | 数量 | 说明 |")
    output.append("|--------|------|------|")
    output.append(f"| Critical | {severity_counts['critical']} | 核心层 - 必须立即修复 |")
    output.append(f"| High | {severity_counts['high']} | API 层 - 应该尽快修复 |")
    output.append(f"| Medium | {severity_counts['medium']} | 脚本层 - 建议修复 |")
    output.append("")
    
    # 按库统计
    library_counts = Counter(v.library for v in violations)
    output.append("## 按数据源统计")
    output.append("")
    for lib, count in library_counts.most_common():
        output.append(f"- **{lib}**: {count} 处")
    output.append("")
    
    # 详细列表
    for severity in ['critical', 'high', 'medium']:
        items = [v for v in violations if v.severity == severity]
        if not items:
            continue
        
        output.append(f"## {severity.upper()} 严重性 ({len(items)} 处)")
        output.append("")
        
        for item in items[:30]:  # 最多显示 30 个
            output.append(f"### {item.file}:{item.line}")
            output.append(f"- **导入**: `{item.import_type}`")
            if item.imported_names:
                output.append(f"- **导入内容**: {', '.join(item.imported_names)}")
            output.append(f"- **建议**: {item.suggestion}")
            output.append("")
        
        if len(items) > 30:
            output.append(f"... 还有 {len(items) - 30} 处")
            output.append("")
    
    return "\n".join(output)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='查找直接导入数据源的违规代码')
    parser.add_argument('--output', type=Path,
                        help='输出 JSON 文件路径')
    parser.add_argument('--root', type=Path, default=Path('.'),
                        help='项目根目录')
    
    args = parser.parse_args()
    
    print(f"Scanning {args.root}...", file=sys.stderr)
    violations = scan_imports(args.root)
    print(f"Found {len(violations)} import violations", file=sys.stderr)
    
    if args.output:
        # 输出 JSON
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(
                [asdict(v) for v in violations],
                f,
                indent=2,
                ensure_ascii=False
            )
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        # 输出文本报告
        print(format_report(violations))

if __name__ == '__main__':
    main()
