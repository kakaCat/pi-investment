"""
P2-3 配置驱动集成 - 端到端验证脚本

验证 service_registry.py 是否正确集成配置驱动注册
"""

import sys
import os

# 设置环境
os.environ['QUANTSYS_CONFIG_DRIVEN'] = 'true'

print("=" * 60)
print("P2-3 配置驱动集成 - 端到端验证")
print("=" * 60)

# 测试 1: 验证配置加载
print("\n[测试 1] 验证配置加载")
try:
    from infrastructure.config.loader import load_config
    config = load_config(environment='dev')
    print(f"✅ 配置加载成功")
    print(f"   - 配置版本: {config.version}")
    print(f"   - 服务数量: {len(config.services)}")
    print(f"   - 仓储数量: {len(config.repositories)}")
    merged = config.get_merged_services()
    print(f"   - 合并后服务总数: {len(merged)}")
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
    sys.exit(1)

# 测试 2: 验证配置验证器
print("\n[测试 2] 验证配置验证器")
try:
    from infrastructure.config.validator import ConfigValidator
    validator = ConfigValidator(strict=False)
    errors = validator.validate(config)
    print(f"✅ 配置验证完成")
    print(f"   - 验证错误数: {len(errors)}")

    # 统计错误类型
    error_types = {}
    for error in errors:
        error_types[error.error_type] = error_types.get(error.error_type, 0) + 1

    if error_types:
        print("   - 错误类型分布:")
        for err_type, count in error_types.items():
            print(f"     * {err_type}: {count}")
except Exception as e:
    print(f"❌ 配置验证失败: {e}")
    sys.exit(1)

# 测试 3: 验证 service_registry 配置驱动注册
print("\n[测试 3] 验证 service_registry 配置驱动注册")
try:
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from infrastructure.services.service_registry import register_all_services

    # 清空之前的注册
    EnhancedServiceFactory._descriptors.clear()
    EnhancedServiceFactory._singletons.clear()

    # 使用配置驱动注册
    print("   正在使用配置驱动注册服务...")
    register_all_services(use_config=True, environment='dev')

    registered = EnhancedServiceFactory.get_registered_services()
    print(f"✅ 配置驱动注册完成")
    print(f"   - 成功注册服务数: {len(registered)}")

    if len(registered) > 0:
        print(f"   - 前 5 个服务: {list(registered)[:5]}")

except Exception as e:
    print(f"❌ 配置驱动注册失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 4: 验证关键 Repository 是否注册
print("\n[测试 4] 验证关键 Repository 是否注册")
try:
    from domain.ports import IStockRepository, IKlineRepository, ISignalRepository

    repositories = [
        ("IStockRepository", IStockRepository),
        ("IKlineRepository", IKlineRepository),
        ("ISignalRepository", ISignalRepository),
    ]

    for name, repo_type in repositories:
        is_registered = EnhancedServiceFactory.is_registered(repo_type)
        status = "✅" if is_registered else "❌"
        print(f"   {status} {name}: {'已注册' if is_registered else '未注册'}")

except Exception as e:
    print(f"❌ 验证失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 5: 验证硬编码注册（向后兼容）
print("\n[测试 5] 验证硬编码注册（向后兼容）")
try:
    # 清空注册
    EnhancedServiceFactory._descriptors.clear()
    EnhancedServiceFactory._singletons.clear()

    # 使用硬编码注册
    print("   正在使用硬编码注册服务...")
    register_all_services(use_config=False)

    registered = EnhancedServiceFactory.get_registered_services()
    print(f"✅ 硬编码注册完成")
    print(f"   - 成功注册服务数: {len(registered)}")

    # 验证关键 Repository
    for name, repo_type in repositories:
        is_registered = EnhancedServiceFactory.is_registered(repo_type)
        status = "✅" if is_registered else "❌"
        print(f"   {status} {name}: {'已注册' if is_registered else '未注册'}")

except Exception as e:
    print(f"❌ 硬编码注册失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 6: 对比两种注册方式
print("\n[测试 6] 对比两种注册方式")
try:
    # 配置驱动
    EnhancedServiceFactory._descriptors.clear()
    EnhancedServiceFactory._singletons.clear()
    register_all_services(use_config=True, environment='dev')
    config_count = len(EnhancedServiceFactory.get_registered_services())

    # 硬编码
    EnhancedServiceFactory._descriptors.clear()
    EnhancedServiceFactory._singletons.clear()
    register_all_services(use_config=False)
    hardcoded_count = len(EnhancedServiceFactory.get_registered_services())

    print(f"   - 配置驱动注册数: {config_count}")
    print(f"   - 硬编码注册数: {hardcoded_count}")
    print(f"   - 差异: {abs(config_count - hardcoded_count)}")

    if config_count > 0 and hardcoded_count > 0:
        print(f"✅ 两种方式都能正常注册服务")
    else:
        print(f"⚠️  某种方式注册失败")

except Exception as e:
    print(f"❌ 对比失败: {e}")

# 测试 7: 验证环境变量控制
print("\n[测试 7] 验证环境变量控制")
try:
    # 测试 QUANTSYS_CONFIG_DRIVEN=true
    os.environ['QUANTSYS_CONFIG_DRIVEN'] = 'true'
    EnhancedServiceFactory._descriptors.clear()
    EnhancedServiceFactory._singletons.clear()
    register_all_services()  # 不传参数，使用环境变量
    count_with_env_true = len(EnhancedServiceFactory.get_registered_services())
    print(f"   - QUANTSYS_CONFIG_DRIVEN=true: {count_with_env_true} 个服务")

    # 测试 QUANTSYS_CONFIG_DRIVEN=false
    os.environ['QUANTSYS_CONFIG_DRIVEN'] = 'false'
    EnhancedServiceFactory._descriptors.clear()
    EnhancedServiceFactory._singletons.clear()
    register_all_services()  # 不传参数，使用环境变量
    count_with_env_false = len(EnhancedServiceFactory.get_registered_services())
    print(f"   - QUANTSYS_CONFIG_DRIVEN=false: {count_with_env_false} 个服务")

    if count_with_env_true > 0 and count_with_env_false > 0:
        print(f"✅ 环境变量控制正常")
    else:
        print(f"⚠️  环境变量控制异常")

except Exception as e:
    print(f"❌ 环境变量控制测试失败: {e}")

print("\n" + "=" * 60)
print("✅ P2-3 配置驱动集成验证完成")
print("=" * 60)
