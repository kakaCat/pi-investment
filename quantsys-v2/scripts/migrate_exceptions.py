"""异常处理迁移脚本

分析并辅助将裸 except Exception 迁移到具体的异常类型

使用方式:
    # 分析所有需要迁移的文件
    python scripts/migrate_exceptions.py --analyze

    # 生成迁移报告
    python scripts/migrate_exceptions.py --report

    # 对特定目录进行迁移（干跑，不实际修改）
    python scripts/migrate_exceptions.py --migrate application/services --dry-run

    # 实际执行迁移
    python scripts/migrate_exceptions.py --migrate application/services
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# 排除的目录
EXCLUDED_DIRS = {
    'venv', '__pycache__', '.git', 'archived_scripts', 
    'examples', 'tests', 'tools', 'debug_scripts'
}

# 异常类型映射规则
EXCEPTION_PATTERNS = {
    # 数据库相关
    r'(pool|connection|session|query|database|sql)': 'DatabaseError',
    # 外部服务
    r'(akshare|tushare|eastmoney|sina|request|http|api|provider)': 'ExternalServiceError',
    # 参数验证
    r'(invalid|validate|param|argument|required)': 'ValidationError',
    # 资源不存在
    r'(not found|does not exist|missing|no such)': 'NotFoundError',
    # 冲突
    r'(already exists|duplicate|conflict)': 'ConflictError',
}


def should_process(filepath: Path) -> bool:
    """判断文件是否需要处理"""
    parts = filepath.parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return False
    return filepath.suffix == '.py'


def analyze_except_block(lines: List[str], start_idx: int) -> Dict:
    """分析一个 except 块的上下文
    
    返回:
        {
            'line': 行号,
            'context': 上下文代码（前后各3行）,
            'suggested_type': 建议的异常类型,
            'confidence': 置信度 (high/medium/low)
        }
    """
    # 获取上下文
    context_start = max(0, start_idx - 3)
    context_end = min(len(lines), start_idx + 4)
    context_lines = lines[context_start:context_end]
    context = ''.join(context_lines)
    
    # 分析建议的异常类型
    suggested_type = 'DomainError'  # 默认
    confidence = 'low'
    
    for pattern, exception_type in EXCEPTION_PATTERNS.items():
        if re.search(pattern, context, re.IGNORECASE):
            suggested_type = exception_type
            confidence = 'medium'
            break
    
    return {
        'line': start_idx + 1,
        'context': context,
        'suggested_type': suggested_type,
        'confidence': confidence
    }


def analyze_file(filepath: Path) -> Dict:
    """分析文件中的 except Exception 使用情况"""
    try:
        content = filepath.read_text(encoding='utf-8')
        lines = content.split('\n')
    except Exception as e:
        return {'error': str(e)}
    
    results = []
    for i, line in enumerate(lines):
        # 匹配 except Exception 模式
        if re.match(r'\s*except\s+Exception\s*(as\s+\w+)?:', line):
            analysis = analyze_except_block(lines, i)
            results.append(analysis)
    
    return {
        'file': str(filepath),
        'count': len(results),
        'exceptions': results
    }


def generate_report(root_dir: Path) -> Dict:
    """生成完整的迁移报告"""
    report = {
        'total_files': 0,
        'total_exceptions': 0,
        'by_directory': {},
        'by_suggested_type': {}
    }
    
    for pyfile in root_dir.rglob('*.py'):
        if not should_process(pyfile):
            continue
        
        analysis = analyze_file(pyfile)
        if 'error' in analysis or analysis['count'] == 0:
            continue
        
        report['total_files'] += 1
        report['total_exceptions'] += analysis['count']
        
        # 按目录统计
        rel_path = pyfile.relative_to(root_dir)
        dir_name = str(rel_path.parts[0]) if rel_path.parts else 'root'
        if dir_name not in report['by_directory']:
            report['by_directory'][dir_name] = {'files': 0, 'exceptions': 0}
        report['by_directory'][dir_name]['files'] += 1
        report['by_directory'][dir_name]['exceptions'] += analysis['count']
        
        # 按建议类型统计
        for exc in analysis['exceptions']:
            exc_type = exc['suggested_type']
            if exc_type not in report['by_suggested_type']:
                report['by_suggested_type'][exc_type] = 0
            report['by_suggested_type'][exc_type] += 1
    
    return report


def print_report(report: Dict):
    """打印迁移报告"""
    print("\n" + "="*60)
    print("异常处理迁移分析报告")
    print("="*60)
    print(f"\n总计:")
    print(f"  文件数: {report['total_files']}")
    print(f"  except Exception 数量: {report['total_exceptions']}")
    
    print(f"\n按目录分布:")
    for dir_name, stats in sorted(report['by_directory'].items(), 
                                   key=lambda x: x[1]['exceptions'], 
                                   reverse=True):
        print(f"  {dir_name:40} {stats['exceptions']:4d} 个 ({stats['files']} 文件)")
    
    print(f"\n建议的异常类型分布:")
    for exc_type, count in sorted(report['by_suggested_type'].items(), 
                                   key=lambda x: x[1], 
                                   reverse=True):
        print(f"  {exc_type:30} {count:4d} 个")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description='异常处理迁移工具')
    parser.add_argument('--analyze', action='store_true', help='分析所有文件')
    parser.add_argument('--report', action='store_true', help='生成迁移报告')
    parser.add_argument('--migrate', type=str, help='迁移指定目录')
    parser.add_argument('--dry-run', action='store_true', help='干跑模式（不实际修改）')
    
    args = parser.parse_args()
    
    root = Path(__file__).resolve().parent.parent
    
    if args.report or args.analyze:
        report = generate_report(root)
        print_report(report)
    
    elif args.migrate:
        print(f"迁移功能尚未实现")
        print(f"目标目录: {args.migrate}")
        print(f"干跑模式: {args.dry_run}")
        print("\n建议:")
        print("1. 先运行 --report 了解分布")
        print("2. 手动修改高频文件")
        print("3. 使用 IDE 的查找替换功能批量处理简单情况")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
