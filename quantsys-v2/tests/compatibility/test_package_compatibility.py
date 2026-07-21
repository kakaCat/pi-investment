#!/usr/bin/env python
"""
测试新增Python包与 Python 3.12.8 的兼容性

测试包列表：
- backtrader>=1.9.78
- alphalens-reloaded>=0.4.3
- empyrical-reloaded>=0.5.9
- lightgbm>=4.0.0
- scikit-optimize>=0.9.0
- baostock>=0.8.9
- TA-Lib>=0.4.28 (已安装)
"""

import sys
import subprocess

def test_package_compatibility(package_name, import_name=None):
    """测试单个包的兼容性"""
    if import_name is None:
        import_name = package_name.replace('-', '_')

    print(f"\n{'='*60}")
    print(f"测试: {package_name}")
    print(f"{'='*60}")

    # 1. 尝试安装（dry-run）
    print(f"📦 检查安装兼容性...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", package_name],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ 安装检查失败:")
        print(result.stderr)
        return False

    print(f"✅ 安装兼容性检查通过")

    # 2. 检查是否已安装
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", package_name.split('>=')[0].split('==')[0]],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"✅ 包已安装")
        # 提取版本信息
        for line in result.stdout.split('\n'):
            if line.startswith('Version:'):
                print(f"   版本: {line.split(':')[1].strip()}")

        # 3. 尝试导入
        print(f"🔍 测试导入...")
        try:
            __import__(import_name)
            print(f"✅ 导入成功")
            return True
        except ImportError as e:
            print(f"❌ 导入失败: {e}")
            return False
    else:
        print(f"⏭️  包未安装（稍后安装）")
        return None

def main():
    print("="*60)
    print("Python 包兼容性测试")
    print("="*60)
    print(f"Python 版本: {sys.version}")
    print(f"Python 路径: {sys.executable}")
    print()

    packages = [
        # (package_name, import_name)
        ("TA-Lib>=0.4.28", "talib"),
        ("backtrader>=1.9.78", "backtrader"),
        ("alphalens-reloaded>=0.4.3", "alphalens"),
        ("empyrical-reloaded>=0.5.9", "empyrical"),
        ("lightgbm>=4.0.0", "lightgbm"),
        ("scikit-optimize>=0.9.0", "skopt"),
        ("baostock>=0.8.9", "baostock"),
        ("matplotlib>=3.7.0", "matplotlib"),
        ("seaborn>=0.12.0", "seaborn"),
    ]

    results = {}
    for package_name, import_name in packages:
        result = test_package_compatibility(package_name, import_name)
        results[package_name] = result

    # 汇总报告
    print("\n" + "="*60)
    print("兼容性测试汇总")
    print("="*60)

    installed = []
    compatible = []
    failed = []

    for package, result in results.items():
        package_short = package.split('>=')[0]
        if result is True:
            installed.append(package_short)
        elif result is None:
            compatible.append(package_short)
        else:
            failed.append(package_short)

    print(f"\n✅ 已安装并兼容 ({len(installed)}):")
    for pkg in installed:
        print(f"   - {pkg}")

    print(f"\n⏭️  未安装（兼容性检查通过）({len(compatible)}):")
    for pkg in compatible:
        print(f"   - {pkg}")

    if failed:
        print(f"\n❌ 兼容性问题 ({len(failed)}):")
        for pkg in failed:
            print(f"   - {pkg}")

    # 生成安装命令
    if compatible:
        print("\n" + "="*60)
        print("📦 安装命令")
        print("="*60)
        print("\n批量安装所有未安装的包:")
        print(f"\npip install {' '.join(compatible)}")

        print("\n或逐个安装:")
        for pkg in compatible:
            print(f"pip install {pkg}")

    print("\n" + "="*60)
    print("✅ 测试完成")
    print("="*60)

    if failed:
        print(f"\n⚠️  发现 {len(failed)} 个不兼容的包，需要进一步检查")
        return 1
    else:
        print(f"\n🎉 所有包与 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} 兼容！")
        return 0

if __name__ == "__main__":
    sys.exit(main())
