#!/usr/bin/env python3
"""
测试核心任务脚本

快速测试三个核心任务是否正常工作：
1. 因子计算
2. 信号生成
3. 风险检查
"""

import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def run_script(script_name: str, description: str):
    """运行脚本并显示结果"""
    return run_command(['python3', str(PROJECT_ROOT / 'scripts' / script_name)], description)


def run_command(command: list[str], description: str):
    """运行命令并显示结果"""
    print("=" * 60)
    print(f"测试: {description}")
    print("=" * 60)
    print()

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=300  # 5分钟超时
        )

        if result.returncode == 0:
            print(result.stdout)
            print(f"\n✅ {description} 测试通过")
        else:
            print(result.stderr)
            print(f"\n❌ {description} 测试失败")
            return False

    except subprocess.TimeoutExpired:
        print(f"\n❌ {description} 超时")
        return False
    except Exception as e:
        print(f"\n❌ {description} 异常: {e}")
        return False

    print()
    return True


def main():
    print("=" * 60)
    print("量化系统核心任务测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    results = []

    # 测试1: 数据更新
    print("📊 测试 1/4: 数据更新")
    print("提示: 首次运行可先执行 python3 quantsys/data/pipeline.py full --market A 获取股票列表和K线数据")
    input("按 Enter 继续...")
    print()
    results.append(run_command(
        ['python3', 'quantsys/data/pipeline.py', 'update-klines'],
        '数据更新'
    ))

    # 测试2: 因子计算
    print("📊 测试 2/4: 因子计算")
    input("按 Enter 继续...")
    print()
    results.append(run_script('calculate_factors.py', '因子计算'))

    # 测试3: 信号生成
    print("📊 测试 3/4: 信号生成")
    input("按 Enter 继续...")
    print()
    results.append(run_script('generate_signals.py', '信号生成'))

    # 测试4: 风险检查
    print("📊 测试 4/4: 风险检查")
    print("提示: 如果没有持仓，此测试会跳过")
    input("按 Enter 继续...")
    print()
    results.append(run_script('risk_check.py', '风险检查'))

    # 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print()

    tests = [
        '数据更新',
        '因子计算',
        '信号生成',
        '风险检查'
    ]

    for i, (test_name, result) in enumerate(zip(tests, results), 1):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{i}. {test_name}: {status}")

    print()

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 所有测试通过！({passed}/{total})")
    else:
        print(f"⚠️  部分测试失败 ({passed}/{total})")

    print()


if __name__ == '__main__':
    main()
