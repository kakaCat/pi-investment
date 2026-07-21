#!/usr/bin/env python3
"""
Redis缓存初始化脚本

用于初始化Redis缓存服务，测试连接，并提供缓存管理功能。
"""
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.config import create_cache_service, create_redis_client
from infrastructure.config import get_redis_config, CACHE_TTL, CACHE_NAMESPACE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_redis_connection():
    """测试Redis连接"""
    logger.info("测试Redis连接...")

    config = get_redis_config()
    logger.info(f"Redis配置: {config['host']}:{config['port']}, DB={config['db']}")

    client = create_redis_client()
    if client:
        logger.info("✓ Redis连接成功")

        # 测试基本操作
        client.set("test_key", "test_value")
        value = client.get("test_key")
        assert value == "test_value", "Redis读写测试失败"
        client.delete("test_key")

        logger.info("✓ Redis读写测试通过")

        # 获取Redis信息
        info = client.info('server')
        logger.info(f"Redis版本: {info.get('redis_version', 'unknown')}")

        return True
    else:
        logger.error("✗ Redis连接失败")
        return False


def test_cache_service():
    """测试缓存服务"""
    logger.info("\n测试缓存服务...")

    cache = create_cache_service(use_redis=True)
    stats = cache.get_stats()

    logger.info(f"缓存后端: {stats['backend']}")

    # 测试缓存操作
    cache.set("test", "key1", {"data": "value1"}, ttl=60)
    result = cache.get("test", "key1")
    assert result == {"data": "value1"}, "缓存读写测试失败"

    logger.info("✓ 缓存服务测试通过")

    # 显示统计
    stats = cache.get_stats()
    logger.info(f"缓存统计: {stats}")

    return cache


def show_cache_config():
    """显示缓存配置"""
    logger.info("\n缓存配置:")
    logger.info("=" * 50)

    logger.info("\nTTL配置:")
    for key, value in CACHE_TTL.items():
        logger.info(f"  {key}: {value}秒 ({value//60}分钟)")

    logger.info("\n命名空间:")
    for key, value in CACHE_NAMESPACE.items():
        logger.info(f"  {key}: {value}")


def clear_cache(namespace: str = None):
    """清除缓存"""
    cache = create_cache_service(use_redis=True)

    if namespace:
        count = cache.clear_namespace(namespace)
        logger.info(f"已清除命名空间 '{namespace}' 的 {count} 条缓存")
    else:
        cache.clear_all()
        logger.info("已清除所有缓存")


def show_cache_stats():
    """显示缓存统计"""
    cache = create_cache_service(use_redis=True)
    stats = cache.get_stats()

    logger.info("\n缓存统计:")
    logger.info("=" * 50)
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")


def warm_up_cache():
    """预热缓存（示例）"""
    logger.info("\n预热缓存...")

    from application.services.data_service import DataService

    cache = create_cache_service(use_redis=True)
    ds = DataService(cache_manager=cache)

    # 这里可以添加预热逻辑，例如：
    # - 加载热门股票的最新数据
    # - 加载市场概览
    # - 加载投资组合数据

    logger.info("缓存预热完成")


def main():
    parser = argparse.ArgumentParser(description='Redis缓存管理工具')
    parser.add_argument('command', choices=['test', 'config', 'clear', 'stats', 'warmup'],
                        help='命令: test(测试连接), config(显示配置), clear(清除缓存), stats(统计), warmup(预热)')
    parser.add_argument('--namespace', help='命名空间（用于clear命令）')

    args = parser.parse_args()

    try:
        if args.command == 'test':
            success = test_redis_connection()
            if success:
                test_cache_service()
            sys.exit(0 if success else 1)

        elif args.command == 'config':
            show_cache_config()

        elif args.command == 'clear':
            clear_cache(args.namespace)

        elif args.command == 'stats':
            show_cache_stats()

        elif args.command == 'warmup':
            warm_up_cache()

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
