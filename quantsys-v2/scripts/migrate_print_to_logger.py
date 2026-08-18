"""批量将 print() 迁移到 structlog

分析并辅助将 print() 替换为 logger 调用

使用方式:
    # 分析所有需要迁移的文件
    python scripts/migrate_print_to_logger.py --analyze

    # 生成迁移报告
    python scripts/migrate_print_to_logger.py --report

    # 对特定文件进行迁移（干跑）
    python scripts/migrate_print_to_logger.py --migrate application/services/data_service.py --dry-run

    # 实际执行迁移
    python scripts/migrate_print_to_logger.py --migrate application/services/
"""
import re
import sys
from pathlib import Path
from typing import Dict, List
import argparse

# 排除的目录
EXCLUDED_DIRS = {
    'venv', '__pycache__', '.git', 'archived_scripts', 
    'scripts', 'tools', 'examples', 'tests', 'live_trading',
    'debug_scripts'
}

# 排除的文件前缀
EXCLUDED_PREFIXES = ('debug_', 'diagnose_', 'test_', 'fix_', 'temp_')


def should_process(filepath: Path) -> bool:
    """判断文件是否需要处理"""
    parts = filepath.parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return False
    if any(filepath.name.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    return filepath.suffix == '.py'


def analyze_print_usage(filepath: Path) -> Dict:
    """分析文件中的 print() 使用情况"""
    try:
        content = filepath.read_text(encoding='utf-8')
        lines = content.split('\n')
    except Exception as e:
        return {'error': str(e)}
    
    print_calls = []
    has_logger = False
    has_structlog_import = False
    
    for i, line in enumerate(lines):
        # 检查是否已有 logger 定义
        if re.search(r'logger\s*=\s*structlog\.get_logger', line):
            has_logger = True
        if 'import structlog' in line or 'from structlog' in line:
            has_structlog_import = True
        
        # 匹配 print() 调用
        if re.search(r'\bprint\s*\(', line):
            print_calls.append({
                'line': i + 1,
                'content': line.strip()
            })
    
    return {
        'file': str(filepath),
        'count': len(print_calls),
        'has_logger': has_logger,
        'has_structlog_import': has_structlog_import,
        'print_calls': print_calls
    }


def generate_report(root_dir: Path) -> Dict:
    """生成完整的迁移报告"""
    report = {
        'total_files': 0,
        'total_prints': 0,
        'files_with_logger': 0,
        'files_without_logger': 0,
        'by_directory': {}
    }
    
    for pyfile in root_dir.rglob('*.py'):
        if not should_process(pyfile):
            continue
        
        analysis = analyze_print_usage(pyfile)
        if 'error' in analysis or analysis['count'] == 0:
            continue
        
        report['total_files'] += 1
        report['total_prints'] += analysis['count']
        
        if analysis['has_logger']:
            report['files_with_logger'] += 1
        else:
            report['files_without_logger'] += 1
        
        # 按目录统计
        rel_path = pyfile.relative_to(root_dir)
        dir_name = str(rel_path.parts[0]) if rel_path.parts else 'root'
        if dir_name not in report['by_directory']:
            report['by_directory'][dir_name] = {'files': 0, 'prints': 0}
        report['by_directory'][dir_name]['files'] += 1
        report['by_directory'][dir_name]['prints'] += analysis['count']
    
    return report


def print_report(report: Dict):
    """打印迁移报告"""
    print("\n" + "="*60)
    print("print() 迁移分析报告")
    print("="*60)
    print(f"\n总计:")
    print(f"  文件数: {report['total_files']}")
    print(f"  print() 调用数: {report['total_prints']}")
    print(f"  已有 logger 的文件: {report['files_with_logger']}")
    print(f"  需添加 logger 的文件: {report['files_without_logger']}")
    
    print(f"\n按目录分布:")
    for dir_name, stats in sorted(report['by_directory'].items(), 
                                   key=lambda x: x[1]['prints'], 
                                   reverse=True):
        print(f"  {dir_name:40} {stats['prints']:4d} 个 ({stats['files']} 文件)")
    
    print("\n" + "="*60)
    print("\n建议:")
    print("1. 先手动修改核心服务文件（application/services/）")
    print("2. 使用 IDE 查找替换功能批量处理简单情况")
    print("3. 保留脚本和工具中的 print（已在 .ruff.toml 豁免）")
    print("="*60)


def add_logger_import(content: str) -> str:
    """在文件顶部添加 logger 定义"""
    lines = content.split('\n')
    
    # 找到最后一个 import 语句
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import_idx = i
    
    if last_import_idx >= 0:
        # 在最后一个 import 后添加空行和 logger 定义
        lines.insert(last_import_idx + 1, '')
        lines.insert(last_import_idx + 2, 'import structlog')
        lines.insert(last_import_idx + 3, 'logger = structlog.get_logger(__name__)')
    else:
        # 没有 import，在文件开头添加
        lines.insert(0, 'import structlog')
        lines.insert(1, 'logger = structlog.get_logger(__name__)')
        lines.insert(2, '')
    
    return '\n'.join(lines)


def migrate_file(filepath: Path, dry_run: bool = True) -> Dict:
    """迁移单个文件中的 print() 到 logger
    
    Args:
        filepath: 文件路径
        dry_run: 是否为干跑模式（不实际修改文件）
    
    Returns:
        迁移结果字典
    """
    analysis = analyze_print_usage(filepath)
    
    if 'error' in analysis:
        return {'success': False, 'error': analysis['error']}
    
    if analysis['count'] == 0:
        return {'success': True, 'migrated': 0, 'message': 'No print() found'}
    
    try:
        content = filepath.read_text(encoding='utf-8')
        
        # 如果没有 logger，先添加
        if not analysis['has_logger']:
            content = add_logger_import(content)
        
        # 简单替换模式（复杂情况需要手动处理）
        # print("message") → logger.info("message")
        # print(f"...") → logger.info("...")
        
        modified_count = 0
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            if re.search(r'\bprint\s*\(', line):
                # 简单替换（保留缩进）
                indent = len(line) - len(line.lstrip())
                # 添加 TODO 标记，需要人工检查
                new_lines.append(' ' * indent + '# TODO: migrate print → logger')
                new_lines.append(line)
                modified_count += 1
            else:
                new_lines.append(line)
        
        new_content = '\n'.join(new_lines)
        
        if not dry_run:
            filepath.write_text(new_content, encoding='utf-8')
        
        return {
            'success': True,
            'migrated': modified_count,
            'message': f"Added TODO markers for {modified_count} print() calls"
        }
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(description='print() 迁移工具')
    parser.add_argument('--analyze', action='store_true', help='分析所有文件')
    parser.add_argument('--report', action='store_true', help='生成迁移报告')
    parser.add_argument('--migrate', type=str, help='迁移指定文件或目录')
    parser.add_argument('--dry-run', action='store_true', help='干跑模式（不实际修改）')
    
    args = parser.parse_args()
    
    root = Path(__file__).resolve().parent.parent
    
    if args.report or args.analyze:
        report = generate_report(root)
        print_report(report)
    
    elif args.migrate:
        target = Path(args.migrate)
        if not target.is_absolute():
            target = root / target
        
        if not target.exists():
            print(f"错误: 路径不存在: {target}")
            return
        
        if target.is_file():
            result = migrate_file(target, dry_run=args.dry_run)
            print(f"\n{'[DRY RUN] ' if args.dry_run else ''}迁移结果:")
            print(f"  文件: {target}")
            print(f"  成功: {result['success']}")
            print(f"  迁移数: {result.get('migrated', 0)}")
            if 'error' in result:
                print(f"  错误: {result['error']}")
        else:
            # 目录，递归处理
            total = 0
            success = 0
            for pyfile in target.rglob('*.py'):
                if should_process(pyfile):
                    result = migrate_file(pyfile, dry_run=args.dry_run)
                    total += 1
                    if result['success']:
                        success += 1
            
            print(f"\n{'[DRY RUN] ' if args.dry_run else ''}批量迁移完成:")
            print(f"  处理文件数: {total}")
            print(f"  成功: {success}")
            print(f"  失败: {total - success}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
