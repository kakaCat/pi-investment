#!/usr/bin/env python3
"""
Agent数据迁移脚本：从JSON文件迁移到PostgreSQL
"""
import os
import sys
import json
import uuid
import psycopg2
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dateutil import parser
from psycopg2.extras import RealDictCursor


class MigrationConfig:
    """迁移配置"""

    def __init__(self):
        # PostgreSQL连接配置
        self.pg_host = os.getenv('POSTGRES_HOST', 'localhost')
        self.pg_port = os.getenv('POSTGRES_PORT', '5432')
        self.pg_db = os.getenv('POSTGRES_DB', 'pi_investment')
        self.pg_user = os.getenv('POSTGRES_USER', 'postgres')
        self.pg_password = os.getenv('POSTGRES_PASSWORD')

        # JSON文件路径
        self.project_root = Path(__file__).parent.parent.parent
        self.json_dir = self.project_root / '.pi-invest'
        self.portfolio_file = self.json_dir / 'portfolio.json'
        self.watchlist_file = self.json_dir / 'watchlist.json'
        self.trades_file = self.json_dir / 'trades.json'
        self.orders_file = self.json_dir / 'orders.json'
        self.cash_file = self.json_dir / 'cash.json'

    def validate(self) -> bool:
        """验证配置"""
        if not self.pg_password:
            print("❌ POSTGRES_PASSWORD环境变量未设置")
            return False

        if not self.json_dir.exists():
            print(f"❌ JSON目录不存在: {self.json_dir}")
            return False

        required_files = [
            self.portfolio_file,
            self.watchlist_file,
            self.trades_file,
            self.cash_file
        ]

        for file_path in required_files:
            if not file_path.exists():
                print(f"❌ JSON文件不存在: {file_path}")
                return False

        return True


class DataLoader:
    """JSON数据加载器"""

    def __init__(self, config: MigrationConfig):
        self.config = config

    def load_portfolio(self) -> List[Dict]:
        """加载持仓数据"""
        with open(self.config.portfolio_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('holdings', [])

    def load_watchlist(self) -> List[Dict]:
        """加载关注列表"""
        with open(self.config.watchlist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('items', [])

    def load_trades(self) -> List[Dict]:
        """加载交易历史"""
        with open(self.config.trades_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('trades', [])

    def load_cash(self) -> Dict:
        """加载现金数据"""
        with open(self.config.cash_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def parse_date(self, date_str: str) -> datetime:
        """解析日期字符串"""
        if not date_str:
            return datetime.now()
        return parser.parse(date_str)


class SchemaUpdater:
    """数据库Schema更新器"""

    def __init__(self, config: MigrationConfig):
        self.config = config

    def update_schema(self, conn) -> bool:
        """执行Schema更新"""
        cursor = conn.cursor()

        try:
            # 读取migration SQL文件
            migration_file = Path(__file__).parent.parent / 'quantsys' / 'db' / 'migrations' / '001_add_agent_data_tables.sql'

            if not migration_file.exists():
                print(f"❌ Migration文件不存在: {migration_file}")
                return False

            with open(migration_file, 'r', encoding='utf-8') as f:
                sql = f.read()

            # 执行SQL
            cursor.execute(sql)
            conn.commit()

            print("✅ Schema更新成功")
            return True

        except Exception as e:
            print(f"❌ Schema更新失败: {e}")
            conn.rollback()
            return False

    def verify_schema(self, conn) -> bool:
        """验证Schema更新"""
        cursor = conn.cursor()

        # 检查watchlist表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'quant_agent'
                AND table_name = 'watchlist'
            )
        """)

        if not cursor.fetchone()[0]:
            print("❌ watchlist表不存在")
            return False

        # 检查positions表是否有新字段
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'quant_agent'
            AND table_name = 'positions'
            AND column_name IN ('name', 'market', 'sector', 'notes', 'original_cost', 'total_invested', 'batch_plan')
        """)

        new_columns = [row[0] for row in cursor.fetchall()]
        expected_columns = ['name', 'market', 'sector', 'notes', 'original_cost', 'total_invested', 'batch_plan']

        if len(new_columns) != len(expected_columns):
            print(f"❌ positions表缺少字段: {set(expected_columns) - set(new_columns)}")
            return False

        print("✅ Schema验证通过")
        return True


if __name__ == '__main__':
    # 测试配置
    config = MigrationConfig()
    if not config.validate():
        sys.exit(1)

    # 测试数据加载
    loader = DataLoader(config)
    try:
        portfolio = loader.load_portfolio()
        watchlist = loader.load_watchlist()
        trades = loader.load_trades()
        cash = loader.load_cash()

        print(f"✅ 加载成功:")
        print(f"  - 持仓: {len(portfolio)}条")
        print(f"  - 关注列表: {len(watchlist)}条")
        print(f"  - 交易历史: {len(trades)}条")
        print(f"  - 现金: {cash.get('available_cash', 0)}")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        sys.exit(1)
