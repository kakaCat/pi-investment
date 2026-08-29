#!/usr/bin/env python3
"""批量重构助手 - 自动重构数据源直接导入

这个工具可以自动将直接导入 akshare/tushare 的代码重构为使用 DataProviderManager

Usage:
    python scripts/refactor/batch_refactor_imports.py --dry-run  # 预览
    python scripts/refactor/batch_refactor_imports.py --fix      # 实际修改
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# 重构模式映射
REFACTOR_PATTERNS = {
    # akshare K线数据
    r'ak\.stock_zh_a_hist\(symbol=["\'](\w+)["\'].*?\)': 
        lambda m: f'get_data_provider_manager().get_klines("{m.group(1)}", "daily", start_date, end_date)["data"]',
    
    # akshare 实时行情
    r'ak\.stock_zh_a_spot_em\(\)':
        lambda m: 'get_data_provider_manager().get_quote(symbol)["data"]',
    
    # tushare 日线数据
    r'pro\.daily\(ts_code=["\'](\w+)["\'].*?\)':
        lambda m: f'get_data_provider_manager().get_klines("{m.group(1)}", "daily", start_date, end_date)["data"]',
}

def suggest_refactoring(file_path: Path, content: str) -> List[Tuple[int, str, str]]:
    """为文件提供重构建议
    
    Returns:
        List of (line_number, original, suggested)
    """
    suggestions = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, start=1):
        # 跳过注释
        if line.strip().startswith('#'):
            continue
        
        # 检查每个模式
        for pattern, replacement_func in REFACTOR_PATTERNS.items():
            match = re.search(pattern, line)
            if match:
                try:
                    suggested = replacement_func(match)
                    suggestions.append((i, line.strip(), suggested))
                except Exception as e:
                    print(f"Warning: Failed to generate suggestion for {file_path}:{i}: {e}", file=sys.stderr)
    
    return suggestions

def add_import_if_needed(content: str) -> str:
    """如果需要，添加 DataProviderManager 导入"""
    if 'get_data_provider_manager' in content:
        return content
    
    # 检查是否已有其他导入
    lines = content.split('\n')
    
    # 找到最后一个 import 语句的位置
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(('import ', 'from ')):
            last_import_idx = i
    
    # 在最后一个 import 后添加
    if last_import_idx >= 0:
        import_line = 'from adapters.outbound.datasources.manager import get_data_provider_manager'
        lines.insert(last_import_idx + 1, import_line)
        return '\n'.join(lines)
    
    return content

def refactor_file(file_path: Path, dry_run: bool = True) -> Dict:
    """重构单个文件"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    suggestions = suggest_refactoring(file_path, content)
    
    if not suggestions:
        return {'success': True, 'suggestions': 0}
    
    if dry_run:
        return {
            'success': True,
            'suggestions': len(suggestions),
            'details': suggestions
        }
    
    # 实际修改（简单替换，生产环境需要更复杂的 AST 重写）
    new_content = content
    for line_num, original, suggested in suggestions:
        # 注意：这是简化版本，实际应该使用 AST 重写
        new_content = new_content.replace(original, f"# TODO: Refactor to: {suggested}\n{original}")
    
    # 添加导入
    new_content = add_import_if_needed(new_content)
    
    file_path.write_text(new_content, encoding='utf-8')
    
    return {
        'success': True,
        'suggestions': len(suggestions),
        'modified': True
    }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='批量重构数据源导入')
    parser.add_argument('--fix', action='store_true',
                        help='实际修改文件（默认：预览模式）')
    parser.add_argument('--path', type=Path, default=Path('.'),
                        help='要扫描的目录')
    
    args = parser.parse_args()
    
    dry_run = not args.fix
    
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║           批量重构数据源导入                                              ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    
    if dry_run:
        print("🔍 预览模式 (使用 --fix 实际修改文件)")
    else:
        print("⚠️  修改模式 (将实际修改文件)")
    
    print()
    
    # 扫描文件
    exclude_dirs = {'venv', '__pycache__', '.git', 'tests', 'adapters/outbound/datasources'}
    
    total_files = 0
    total_suggestions = 0
    
    for py_file in args.path.rglob('*.py'):
        if any(part in str(py_file) for part in exclude_dirs):
            continue
        
        result = refactor_file(py_file, dry_run=dry_run)
        
        if result.get('suggestions', 0) > 0:
            total_files += 1
            total_suggestions += result['suggestions']
            
            print(f"\n📁 {py_file.relative_to(args.path)}")
            
            if dry_run and 'details' in result:
                for line_num, original, suggested in result['details'][:3]:  # 最多显示 3 个
                    print(f"  行 {line_num}:")
                    print(f"    原始: {original[:80]}...")
                    print(f"    建议: {suggested[:80]}...")
                
                if len(result['details']) > 3:
                    print(f"  ... 还有 {len(result['details']) - 3} 处建议")
    
    print()
    print("=" * 70)
    print(f"总结: 扫描了 {total_files} 个文件，发现 {total_suggestions} 处需要重构")
    print("=" * 70)
    
    if dry_run and total_suggestions > 0:
        print()
        print("⚠️  注意: 这是自动化工具生成的建议，实际重构时请:")
        print("  1. 仔细检查每处修改")
        print("  2. 运行测试验证功能正确")
        print("  3. 考虑使用 AST 工具进行更精确的重构")
        print()
        print("建议: 优先手动重构核心模块，使用工具辅助扫描")

if __name__ == '__main__':
    main()
