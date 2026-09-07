"""
运行所有示例代码

这个脚本会依次运行所有示例，验证代码的正确性。
"""

import sys
import os
import subprocess
import time

# 示例文件列表
EXAMPLES = [
    ('IC分析示例', 'example_ic_analysis.py'),
    ('因子正交化示例', 'example_orthogonalization.py'),
    ('期权Greeks计算示例', 'example_greeks_calculator.py'),
    ('GPU加速示例', 'example_gpu_factors.py'),
    ('股指期货对冲示例', 'example_index_hedge.py'),
    ('做市策略示例', 'example_market_making.py'),
]


def run_example(name, filename):
    """运行单个示例"""
    print("\n" + "=" * 70)
    print(f"运行: {name}")
    print("=" * 70)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, filename)

    if not os.path.exists(script_path):
        print(f"❌ 文件不存在: {script_path}")
        return False

    try:
        start_time = time.time()

        # 运行示例
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=60  # 60秒超时
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            print(f"✅ 成功 (耗时: {elapsed:.2f}秒)")
            if result.stdout:
                print("\n输出:")
                print(result.stdout[:500])  # 只显示前500字符
                if len(result.stdout) > 500:
                    print("... (输出已截断)")
            return True
        else:
            print(f"❌ 失败 (返回码: {result.returncode})")
            if result.stderr:
                print("\n错误信息:")
                print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ 超时 (>60秒)")
        return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("Quantsys-v2 示例代码测试")
    print("=" * 70)
    print(f"\n共有 {len(EXAMPLES)} 个示例")
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")

    results = []

    for name, filename in EXAMPLES:
        success = run_example(name, filename)
        results.append((name, success))

        # 短暂暂停
        time.sleep(1)

    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    success_count = sum(1 for _, success in results if success)
    total_count = len(results)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}  {name}")

    print("\n" + "-" * 70)
    print(f"通过: {success_count}/{total_count}")
    print(f"成功率: {success_count/total_count*100:.1f}%")

    if success_count == total_count:
        print("\n🎉 所有示例运行成功！")
        return 0
    else:
        print(f"\n⚠️  有 {total_count - success_count} 个示例失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
