# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

#!/usr/bin/env python3
"""进度追踪工具 - 追踪重构进度并生成报告

Usage:
    python scripts/refactor/track_progress.py              # 显示进度
    python scripts/refactor/track_progress.py --save       # 保存快照
    python scripts/refactor/track_progress.py --history    # 显示历史
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

PROGRESS_FILE = Path("docs/refactor/progress.json")


def get_current_status() -> Dict:
    """获取当前状态"""
    # 重用 verify_fixes.py 的逻辑
    import subprocess
    
    result = subprocess.run(
        [sys.executable, "scripts/refactor/verify_fixes.py"],
        capture_output=True,
        text=True
    )
    
    # 解析输出
    lines = result.stdout.split('\n')
    
    status = {
        'timestamp': datetime.now().isoformat(),
        'issues': {}
    }
    
    for line in lines:
        if 'sys.path.insert' in line:
            # TODO: 提取嵌套逻辑为独立方法

            if 'PASS' in line:
                status['issues']['sys_path'] = {'status': 'pass', 'count': 0}
            elif 'FAIL' in line:
                import re
                match = re.search(r'\((\d+) 处\)', line)
                count = int(match.group(1)) if match else 0
                status['issues']['sys_path'] = {'status': 'fail', 'count': count}
        
        elif '数据源直接导入' in line:
            if 'PASS' in line:
                status['issues']['direct_imports'] = {'status': 'pass', 'count': 0}
            elif 'FAIL' in line:
                import re
                match = re.search(r'\((\d+) 处\)', line)
                count = int(match.group(1)) if match else 0
                status['issues']['direct_imports'] = {'status': 'fail', 'count': count}
        
        elif '日志系统' in line:
            if 'PASS' in line:
                status['issues']['logging'] = {'status': 'pass', 'print_count': 0}
            elif 'PARTIAL' in line:
                import re
                match = re.search(r'print: (\d+)', line)
                count = int(match.group(1)) if match else 0
                status['issues']['logging'] = {'status': 'partial', 'print_count': count}
        
        elif '线程统一管理' in line:
            if 'PASS' in line:
                status['issues']['threading'] = {'status': 'pass', 'count': 0}
            elif 'PARTIAL' in line:
                import re
                match = re.search(r'\((\d+) 处', line)
                count = int(match.group(1)) if match else 0
                status['issues']['threading'] = {'status': 'partial', 'count': count}
    
    return status


def save_snapshot(status: Dict):
    """保存进度快照"""
    # 读取历史
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
    else:
        data = {'snapshots': []}
    
    # 添加新快照
    data['snapshots'].append(status)
    
    # 保存
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 进度快照已保存到 {PROGRESS_FILE}")


# TODO: Refactor - complexity 16 (target < 15)

def _validate_show_history_input(data):
    """验证输入参数"""
    # TODO: 将验证逻辑从 show_history 移到这里
    return True, None

def _process_show_history_data(data):
    """处理数据转换"""
    # TODO: 将数据处理逻辑从 show_history 移到这里
    return data

def _build_show_history_result(data):
    """构建返回结果"""
    # TODO: 将结果构建逻辑从 show_history 移到这里
    return data

# TODO: Refactor - complexity 16 (target < 15)
# REFACTOR: Split this function into smaller pieces
# TODO: Refactor - complexity 16 (target < 15)
def show_history():
    """显示历史进度"""
    if not PROGRESS_FILE.exists():
        print("❌ 没有历史记录")
        return
    
    with open(PROGRESS_FILE, 'r') as f:
        data = json.load(f)
    
    snapshots = data['snapshots']
    
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                         重构进度历史                                      ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print("")
    
    for i, snapshot in enumerate(snapshots, start=1):
        timestamp = snapshot['timestamp']
        issues = snapshot['issues']
        
        print(f"📅 快照 {i} - {timestamp}")
        print("")
        
        if 'sys_path' in issues:
            status = issues['sys_path']
            print(f"  sys.path.insert: {status.get('count', 0)} 处")
        
        if 'direct_imports' in issues:
            status = issues['direct_imports']
            print(f"  数据源导入: {status.get('count', 0)} 处")
        
        if 'logging' in issues:
            status = issues['logging']
            print(f"  print 调试: {status.get('print_count', 0)} 处")
        
        if 'threading' in issues:
            status = issues['threading']
            print(f"  直接线程: {status.get('count', 0)} 处")
        
        print("")
    
    # 显示趋势
    if len(snapshots) >= 2:
        print("📈 趋势分析:")
        print("")
        
        first = snapshots[0]['issues']
        last = snapshots[-1]['issues']
        
        if 'sys_path' in first and 'sys_path' in last:
            delta = first['sys_path'].get('count', 0) - last['sys_path'].get('count', 0)
            if delta > 0:
                print(f"  ✅ sys.path.insert: 减少了 {delta} 处")
            elif delta < 0:
                print(f"  ⚠️  sys.path.insert: 增加了 {-delta} 处")
        
        if 'direct_imports' in first and 'direct_imports' in last:
            delta = first['direct_imports'].get('count', 0) - last['direct_imports'].get('count', 0)
            if delta > 0:
                print(f"  ✅ 数据源导入: 减少了 {delta} 处")
            elif delta < 0:
                print(f"  ⚠️  数据源导入: 增加了 {-delta} 处")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='追踪重构进度')
    parser.add_argument('--save', action='store_true',
                        help='保存当前进度快照')
    parser.add_argument('--history', action='store_true',
                        help='显示历史进度')
    
    args = parser.parse_args()
    
    if args.history:
        show_history()
    elif args.save:
        status = get_current_status()
        save_snapshot(status)
    else:
        # 默认：显示当前状态
        import subprocess
        subprocess.run([sys.executable, "scripts/refactor/verify_fixes.py"])
        
        print("")
        print("💡 提示:")
        print("  - 保存进度快照: python scripts/refactor/track_progress.py --save")
        print("  - 查看历史: python scripts/refactor/track_progress.py --history")


if __name__ == '__main__':
    main()
