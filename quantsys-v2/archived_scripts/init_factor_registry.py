#!/usr/bin/env python3
"""
初始化因子注册表
从API读取因子列表并同步到数据库

Usage:
    python scripts/init_factor_registry.py
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List
import requests
import psycopg2
from psycopg2.extras import execute_batch

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API配置
API_BASE_URL = "http://127.0.0.1:5001/api"
FACTORS_LIST_URL = f"{API_BASE_URL}/factors/list"

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'database': 'quant_investment',
    'user': 'mac',
    'password': ''
}


def fetch_factors_from_api() -> Dict:
    """从API获取因子列表"""
    logger.info(f"Fetching factors from API: {FACTORS_LIST_URL}")

    try:
        response = requests.get(FACTORS_LIST_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get('success'):
            raise RuntimeError(f"API returned success=false: {data}")

        return data['data']

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch factors from API: {e}")
        raise


def parse_factors(api_data: Dict) -> List[Dict]:
    """解析API返回的因子数据"""
    factors = []

    categories = api_data.get('categories', {})
    logger.info(f"Found {len(categories)} factor categories")

    for category_key, category_data in categories.items():
        category_name = category_data.get('name', category_key)
        factor_list = category_data.get('factors', [])

        logger.info(f"  - {category_name}: {len(factor_list)} factors")

        for factor_name in factor_list:
            factors.append({
                'name': factor_name,
                'category': category_key,
                'description': f'{category_name}因子',
                'parameters': {},
                'formula': None,
                'data_dependencies': []
            })

    logger.info(f"Total factors to register: {len(factors)}")
    return factors


def sync_to_database(factors: List[Dict]):
    """同步因子到数据库"""
    logger.info("Connecting to database...")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # 插入因子（使用UPSERT避免重复）
        insert_sql = """
            INSERT INTO factor_registry (name, category, description, parameters, formula, data_dependencies)
            VALUES (%(name)s, %(category)s, %(description)s, %(parameters)s::jsonb, %(formula)s, %(data_dependencies)s)
            ON CONFLICT (name) DO UPDATE SET
                category = EXCLUDED.category,
                description = EXCLUDED.description,
                parameters = EXCLUDED.parameters,
                updated_at = NOW()
        """

        # 准备数据（转换为JSON字符串）
        insert_data = []
        for factor in factors:
            insert_data.append({
                'name': factor['name'],
                'category': factor['category'],
                'description': factor['description'],
                'parameters': json.dumps(factor['parameters']),
                'formula': factor['formula'],
                'data_dependencies': factor['data_dependencies']
            })

        logger.info(f"Inserting {len(insert_data)} factors...")
        execute_batch(cursor, insert_sql, insert_data, page_size=100)

        conn.commit()
        logger.info(f"✅ Successfully synced {len(factors)} factors to database")

        # 显示统计信息
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM factor_registry
            GROUP BY category
            ORDER BY count DESC
        """)

        logger.info("\nFactor distribution by category:")
        for row in cursor.fetchall():
            logger.info(f"  - {row[0]}: {row[1]} factors")

        cursor.execute("SELECT COUNT(*) FROM factor_registry")
        total = cursor.fetchone()[0]
        logger.info(f"\nTotal factors in database: {total}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise

    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("初始化因子注册表")
    logger.info("=" * 60)

    try:
        # 1. 从API获取因子
        api_data = fetch_factors_from_api()

        # 2. 解析因子数据
        factors = parse_factors(api_data)

        # 3. 同步到数据库
        sync_to_database(factors)

        logger.info("\n" + "=" * 60)
        logger.info("✅ 因子注册表初始化完成！")
        logger.info("=" * 60)
        logger.info("\n下一步:")
        logger.info("  1. 运行因子计算: python scripts/compute_factors.py")
        logger.info("  2. 验证因子数据: SELECT COUNT(*) FROM factor_data;")

    except KeyboardInterrupt:
        logger.info("\n用户中断，退出...")
        sys.exit(0)

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
