#!/usr/bin/env python3
"""代码质量仪表盘 - 生成可视化的质量指标报告

Usage:
    python scripts/refactor/quality_dashboard.py
    python scripts/refactor/quality_dashboard.py --html
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

def get_metrics() -> Dict:
    """收集所有质量指标"""
    import subprocess
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'issues': {}
    }
    
    # 运行验证脚本获取状态
    result = subprocess.run(
        [sys.executable, 'scripts/refactor/verify_fixes.py'],
        capture_output=True,
        text=True
    )
    
    # 解析输出
    lines = result.stdout.split('\n')
    for line in lines:
        if 'sys.path.insert' in line:
            import re
            match = re.search(r'\((\d+) 处\)', line)
            if match:
                metrics['issues']['sys_path'] = {
                    'count': int(match.group(1)),
                    'status': 'fail' if int(match.group(1)) > 0 else 'pass'
                }
        elif '数据源直接导入' in line:
            import re
            match = re.search(r'\((\d+) 处\)', line)
            if match:
                metrics['issues']['direct_imports'] = {
                    'count': int(match.group(1)),
                    'status': 'fail' if int(match.group(1)) > 0 else 'pass'
                }
        elif 'print:' in line:
            import re
            match = re.search(r'print: (\d+)', line)
            if match:
                metrics['issues']['print_debug'] = {
                    'count': int(match.group(1)),
                    'status': 'fail' if int(match.group(1)) > 0 else 'pass'
                }
    
    # 计算总体评分
    total_issues = sum(
        issue.get('count', 0) 
        for issue in metrics['issues'].values()
    )
    
    # 评分: 0 issues = 100, 每个 issue 扣 0.1 分
    metrics['score'] = max(0, 100 - (total_issues * 0.01))
    
    return metrics

def render_ascii_dashboard(metrics: Dict):
    """渲染 ASCII 仪表盘"""
    score = metrics['score']
    
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                      代码质量仪表盘                                       ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()
    
    # 总体评分
    print(f"📊 总体评分: {score:.1f}/100")
    print()
    
    # 进度条
    bar_length = 50
    filled = int(bar_length * score / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    
    if score >= 90:
        color = '🟢'
    elif score >= 70:
        color = '🟡'
    else:
        color = '🔴'
    
    print(f"{color} [{bar}] {score:.1f}%")
    print()
    
    # 各项指标
    print("📋 问题详情:")
    print()
    
    issues = metrics.get('issues', {})
    
    if 'sys_path' in issues:
        count = issues['sys_path']['count']
        status = '✅' if count == 0 else '❌'
        print(f"  {status} sys.path.insert: {count} 处")
    
    if 'direct_imports' in issues:
        count = issues['direct_imports']['count']
        status = '✅' if count == 0 else '❌'
        print(f"  {status} 数据源直接导入: {count} 处")
    
    if 'print_debug' in issues:
        count = issues['print_debug']['count']
        status = '✅' if count == 0 else '❌'
        print(f"  {status} print 调试: {count} 处")
    
    print()
    
    # 建议
    print("💡 改进建议:")
    print()
    
    suggestions = []
    
    if issues.get('sys_path', {}).get('count', 0) > 0:
        suggestions.append("  • 运行 make fix-syspath 清理 sys.path.insert")
    
    if issues.get('direct_imports', {}).get('count', 0) > 0:
        suggestions.append("  • 运行 make scan-imports 查看详细违规列表")
    
    if issues.get('print_debug', {}).get('count', 0) > 0:
        suggestions.append("  • 将 print() 替换为 logger.info()")
    
    if not suggestions:
        print("  🎉 没有待改进项！代码质量优秀！")
    else:
        for suggestion in suggestions:
            print(suggestion)
    
    print()

def render_html_dashboard(metrics: Dict, output_file: Path):
    """渲染 HTML 仪表盘"""
    score = metrics['score']
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>代码质量仪表盘 - QuantSys V2</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .timestamp {{
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .score {{
            text-align: center;
            margin: 40px 0;
        }}
        .score-value {{
            font-size: 72px;
            font-weight: bold;
            color: {'#4caf50' if score >= 90 else '#ff9800' if score >= 70 else '#f44336'};
        }}
        .progress-bar {{
            width: 100%;
            height: 40px;
            background: #e0e0e0;
            border-radius: 20px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, 
                {'#4caf50' if score >= 90 else '#ff9800' if score >= 70 else '#f44336'} 0%, 
                {'#45a049' if score >= 90 else '#f57c00' if score >= 70 else '#d32f2f'} 100%);
            width: {score}%;
            transition: width 0.5s ease;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
        }}
        .metric-title {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        .metric-value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .metric-pass {{ color: #4caf50; }}
        .metric-fail {{ color: #f44336; }}
        .suggestions {{
            background: #fff3cd;
            border-left: 4px solid #ff9800;
            padding: 20px;
            margin: 30px 0;
        }}
        .suggestions h3 {{
            margin-top: 0;
            color: #856404;
        }}
        .suggestions ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .suggestions li {{
            margin: 8px 0;
            color: #856404;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 代码质量仪表盘</h1>
        <div class="timestamp">更新时间: {metrics['timestamp']}</div>
        
        <div class="score">
            <div class="score-value">{score:.1f}</div>
            <div>总体评分 (满分 100)</div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill"></div>
        </div>
        
        <div class="metrics">
"""
    
    # 添加指标卡片
    issues = metrics.get('issues', {})
    
    if 'sys_path' in issues:
        count = issues['sys_path']['count']
        status = 'pass' if count == 0 else 'fail'
        html += f"""
            <div class="metric-card">
                <div class="metric-title">sys.path.insert</div>
                <div class="metric-value metric-{status}">{count}</div>
                <div>{'✅ 已清理' if count == 0 else '❌ 需要清理'}</div>
            </div>
        """
    
    if 'direct_imports' in issues:
        count = issues['direct_imports']['count']
        status = 'pass' if count == 0 else 'fail'
        html += f"""
            <div class="metric-card">
                <div class="metric-title">数据源直接导入</div>
                <div class="metric-value metric-{status}">{count}</div>
                <div>{'✅ 已清理' if count == 0 else '❌ 需要重构'}</div>
            </div>
        """
    
    if 'print_debug' in issues:
        count = issues['print_debug']['count']
        status = 'pass' if count == 0 else 'fail'
        html += f"""
            <div class="metric-card">
                <div class="metric-title">print 调试语句</div>
                <div class="metric-value metric-{status}">{count}</div>
                <div>{'✅ 已清理' if count == 0 else '❌ 需要替换'}</div>
            </div>
        """
    
    html += """
        </div>
"""
    
    # 添加建议
    suggestions = []
    if issues.get('sys_path', {}).get('count', 0) > 0:
        suggestions.append("运行 <code>make fix-syspath</code> 清理 sys.path.insert")
    if issues.get('direct_imports', {}).get('count', 0) > 0:
        suggestions.append("运行 <code>make scan-imports</code> 查看详细违规列表")
    if issues.get('print_debug', {}).get('count', 0) > 0:
        suggestions.append("将 <code>print()</code> 替换为 <code>logger.info()</code>")
    
    if suggestions:
        html += """
        <div class="suggestions">
            <h3>💡 改进建议</h3>
            <ul>
"""
        for suggestion in suggestions:
            html += f"                <li>{suggestion}</li>\n"
        
        html += """
            </ul>
        </div>
"""
    
    html += """
    </div>
</body>
</html>
"""
    
    output_file.write_text(html, encoding='utf-8')
    print(f"✅ HTML 仪表盘已生成: {output_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='生成代码质量仪表盘')
    parser.add_argument('--html', action='store_true',
                        help='生成 HTML 版本')
    parser.add_argument('--output', type=Path,
                        default=Path('docs/refactor/quality-dashboard.html'),
                        help='HTML 输出文件路径')
    
    args = parser.parse_args()
    
    # 收集指标
    metrics = get_metrics()
    
    if args.html:
        # 生成 HTML
        render_html_dashboard(metrics, args.output)
        print(f"\n在浏览器中打开: file://{args.output.absolute()}")
    else:
        # 显示 ASCII 仪表盘
        render_ascii_dashboard(metrics)

if __name__ == '__main__':
    main()
