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

# 常量定义
SCHEMA_NAME = 'quant_agent'
POSITIONS_NEW_COLUMNS = ['name', 'market', 'sector', 'notes', 'original_cost', 'total_invested', 'batch_plan']


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

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
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
                WHERE table_schema = %s
                AND table_name = 'watchlist'
            )
        """, (SCHEMA_NAME,))

        if not cursor.fetchone()[0]:
            print("❌ watchlist表不存在")
            return False

        # 检查positions表是否有新字段
        placeholders = ','.join(['%s'] * len(POSITIONS_NEW_COLUMNS))
        cursor.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s
            AND table_name = 'positions'
            AND column_name IN ({placeholders})
        """, (SCHEMA_NAME, *POSITIONS_NEW_COLUMNS))

        new_columns = [row[0] for row in cursor.fetchall()]

        if len(new_columns) != len(POSITIONS_NEW_COLUMNS):
            print(f"❌ positions表缺少字段: {set(POSITIONS_NEW_COLUMNS) - set(new_columns)}")
            return False

        print("✅ Schema验证通过")
        return True


class DataMigrator:
    """数据迁移器"""

    def __init__(self, config: MigrationConfig, loader: DataLoader):
        self.config = config
        self.loader = loader

    def migrate_accounts(self, conn) -> bool:
        """迁移账户数据"""
        cursor = conn.cursor()

        try:
            # 从cash.json加载数据
            cash_data = self.loader.load_cash()

            # 检查账户是否已存在
            cursor.execute(f"""
                SELECT account_id FROM {SCHEMA_NAME}.accounts
                WHERE account_name = %s
            """, ('default',))

            if cursor.fetchone():
                print("⚠️  账户已存在，跳过")
                return True

            # 插入账户记录
            cursor.execute(f"""
                INSERT INTO {SCHEMA_NAME}.accounts
                (account_name, balance, currency, notes, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
            """, (
                'default',
                cash_data.get('available_cash', 0),
                'CNY',
                'Migrated from cash.json'
            ))

            conn.commit()
            print(f"✅ 迁移账户: available_cash={cash_data.get('available_cash', 0)}")
            return True

        except Exception as e:
            print(f"❌ 账户迁移失败: {e}")
            conn.rollback()
            return False

    def migrate_positions(self, conn) -> bool:
        """迁移持仓数据"""
        cursor = conn.cursor()

        try:
            # 加载持仓数据
            holdings = self.loader.load_portfolio()

            # 获取账户ID
            cursor.execute(f"""
                SELECT account_id FROM {SCHEMA_NAME}.accounts
                WHERE account_name = %s
            """, ('default',))

            result = cursor.fetchone()
            if not result:
                print("❌ 账户不存在，请先迁移账户")
                return False

            account_id = result[0]
            migrated_count = 0

            for holding in holdings:
                symbol = holding.get('symbol')

                # 检查持仓是否已存在
                cursor.execute(f"""
                    SELECT position_id FROM {SCHEMA_NAME}.positions
                    WHERE symbol = %s AND account_id = %s
                """, (symbol, account_id))

                if cursor.fetchone():
                    print(f"⚠️  持仓已存在: {symbol}，跳过")
                    continue

                # 解析市场前缀
                market = None
                if symbol.startswith(('00', '01', '02', '03', '06', '09')):
                    market = 'HK'
                elif symbol.startswith(('6', '0', '3')):
                    market = 'A'
                # US股票通常是字母开头，但这里没有US股票，保持None

                # 插入持仓记录
                cursor.execute(f"""
                    INSERT INTO {SCHEMA_NAME}.positions
                    (account_id, symbol, name, market, quantity, avg_price,
                     current_price, market_value, cost_basis, unrealized_pnl,
                     unrealized_pnl_pct, sector, notes, original_cost,
                     total_invested, batch_plan, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    account_id,
                    symbol,
                    holding.get('name'),
                    market,
                    holding.get('quantity', 0),
                    holding.get('avg_price', 0),
                    holding.get('current_price', 0),
                    holding.get('market_value', 0),
                    holding.get('cost_basis', 0),
                    holding.get('unrealized_pnl', 0),
                    holding.get('unrealized_pnl_pct', 0),
                    holding.get('sector'),
                    holding.get('notes'),
                    holding.get('original_cost'),
                    holding.get('total_invested'),
                    json.dumps(holding.get('batch_plan')) if holding.get('batch_plan') else None
                ))

                migrated_count += 1

            conn.commit()
            print(f"✅ 迁移持仓: {migrated_count}条")
            return True

        except Exception as e:
            print(f"❌ 持仓迁移失败: {e}")
            conn.rollback()
            return False

    def migrate_watchlist(self, conn) -> bool:
        """迁移关注列表"""
        cursor = conn.cursor()

        try:
            # 加载关注列表
            items = self.loader.load_watchlist()

            migrated_count = 0

            for item in items:
                symbol = item.get('symbol')

                # 检查是否已存在
                cursor.execute(f"""
                    SELECT id FROM {SCHEMA_NAME}.watchlist
                    WHERE symbol = %s
                """, (symbol,))

                if cursor.fetchone():
                    print(f"⚠️  关注列表已存在: {symbol}，跳过")
                    continue

                # 解析市场前缀
                market = None
                if symbol.startswith(('00', '01', '02', '03', '06', '09')):
                    market = 'HK'
                elif symbol.startswith(('6', '0', '3')):
                    market = 'A'

                # 解析日期
                added_date = self.loader.parse_date(item.get('added_date'))

                # 插入关注列表记录
                cursor.execute(f"""
                    INSERT INTO {SCHEMA_NAME}.watchlist
                    (symbol, name, market, pool, priority, status,
                     target_price, stop_loss, notes, tags,
                     added_date, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    symbol,
                    item.get('name'),
                    market,
                    item.get('pool', 'A'),
                    item.get('priority', 3),
                    item.get('status', 'watching'),
                    item.get('target_price'),
                    item.get('stop_loss'),
                    item.get('notes'),
                    json.dumps(item.get('tags')) if item.get('tags') else None,
                    added_date
                ))

                migrated_count += 1

            conn.commit()
            print(f"✅ 迁移关注列表: {migrated_count}条")
            return True

        except Exception as e:
            print(f"❌ 关注列表迁移失败: {e}")
            conn.rollback()
            return False

    def migrate_position_history(self, conn) -> bool:
        """迁移交易历史"""
        cursor = conn.cursor()

        try:
            # 加载交易历史
            trades = self.loader.load_trades()

            # 获取账户ID
            cursor.execute(f"""
                SELECT account_id FROM {SCHEMA_NAME}.accounts
                WHERE account_name = %s
            """, ('default',))

            result = cursor.fetchone()
            if not result:
                print("❌ 账户不存在，请先迁移账户")
                return False

            account_id = result[0]

            # 获取所有持仓的symbol->position_id映射
            cursor.execute(f"""
                SELECT symbol, position_id FROM {SCHEMA_NAME}.positions
                WHERE account_id = %s
            """, (account_id,))

            symbol_to_position_id = {row[0]: row[1] for row in cursor.fetchall()}

            migrated_count = 0
            skipped_count = 0

            for trade in trades:
                symbol = trade.get('symbol')
                trade_id = trade.get('id')

                # 检查是否已存在（通过notes字段存储原始trade_id）
                cursor.execute(f"""
                    SELECT history_id FROM {SCHEMA_NAME}.position_history
                    WHERE notes LIKE %s
                """, (f'%trade_id:{trade_id}%',))

                if cursor.fetchone():
                    print(f"⚠️  交易历史已存在: {trade_id}，跳过")
                    skipped_count += 1
                    continue

                # 获取position_id
                position_id = symbol_to_position_id.get(symbol)
                if not position_id:
                    print(f"⚠️  持仓不存在: {symbol}，跳过交易 {trade_id}")
                    skipped_count += 1
                    continue

                # 解析日期
                trade_date = self.loader.parse_date(trade.get('date'))

                # 计算realized_pnl和realized_pnl_pct（如果是卖出交易）
                action = trade.get('action', 'buy')
                realized_pnl = None
                realized_pnl_pct = None

                if action == 'sell':
                    quantity = trade.get('quantity', 0)
                    price = trade.get('price', 0)
                    cost = trade.get('cost', 0)
                    fee = trade.get('fee', 0)

                    if cost > 0:
                        realized_pnl = (price * quantity) - cost - fee
                        realized_pnl_pct = (realized_pnl / cost) * 100

                # 插入交易历史记录
                cursor.execute(f"""
                    INSERT INTO {SCHEMA_NAME}.position_history
                    (position_id, action, quantity, price, total_amount,
                     fee, trade_date, name, realized_pnl, realized_pnl_pct, notes,
                     created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    position_id,
                    action,
                    trade.get('quantity', 0),
                    trade.get('price', 0),
                    trade.get('total', 0),
                    trade.get('fee', 0),
                    trade_date,
                    trade.get('name'),
                    realized_pnl,
                    realized_pnl_pct,
                    f"trade_id:{trade_id}; {trade.get('notes', '')}"
                ))

                migrated_count += 1

            conn.commit()
            print(f"✅ 迁移交易历史: {migrated_count}条 (跳过{skipped_count}条)")
            return True

        except Exception as e:
            print(f"❌ 交易历史迁移失败: {e}")
            conn.rollback()
            return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Agent数据迁移脚本')
    parser.add_argument('--dry-run', action='store_true', help='仅验证配置和数据，不执行迁移')
    parser.add_argument('--skip-schema', action='store_true', help='跳过Schema更新')
    args = parser.parse_args()

    # 1. 验证配置
    print("=" * 60)
    print("步骤 1/6: 验证配置")
    print("=" * 60)
    config = MigrationConfig()
    if not config.validate():
        sys.exit(1)
    print("✅ 配置验证通过\n")

    # 2. 加载数据
    print("=" * 60)
    print("步骤 2/6: 加载JSON数据")
    print("=" * 60)
    loader = DataLoader(config)
    try:
        portfolio = loader.load_portfolio()
        watchlist = loader.load_watchlist()
        trades = loader.load_trades()
        cash = loader.load_cash()

        print(f"✅ 数据加载成功:")
        print(f"  - 持仓: {len(portfolio)}条")
        print(f"  - 关注列表: {len(watchlist)}条")
        print(f"  - 交易历史: {len(trades)}条")
        print(f"  - 现金: {cash.get('available_cash', 0)} CNY\n")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        sys.exit(1)

    if args.dry_run:
        print("🔍 Dry-run模式，退出")
        sys.exit(0)

    # 3. 连接数据库
    print("=" * 60)
    print("步骤 3/6: 连接PostgreSQL")
    print("=" * 60)
    try:
        conn = psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database=config.pg_db,
            user=config.pg_user,
            password=config.pg_password
        )
        print("✅ 数据库连接成功\n")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)

    try:
        # 4. 更新Schema
        if not args.skip_schema:
            print("=" * 60)
            print("步骤 4/6: 更新数据库Schema")
            print("=" * 60)
            schema_updater = SchemaUpdater(config)
            if not schema_updater.update_schema(conn):
                sys.exit(1)
            if not schema_updater.verify_schema(conn):
                sys.exit(1)
            print()
        else:
            print("⚠️  跳过Schema更新\n")

        # 5. 执行数据迁移
        print("=" * 60)
        print("步骤 5/6: 执行数据迁移")
        print("=" * 60)
        migrator = DataMigrator(config, loader)

        # 迁移顺序：accounts -> positions -> watchlist -> position_history
        if not migrator.migrate_accounts(conn):
            sys.exit(1)

        if not migrator.migrate_positions(conn):
            sys.exit(1)

        if not migrator.migrate_watchlist(conn):
            sys.exit(1)

        if not migrator.migrate_position_history(conn):
            sys.exit(1)

        print()

        # 6. 验证迁移结果
        print("=" * 60)
        print("步骤 6/6: 验证迁移结果")
        print("=" * 60)
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.accounts")
        print(f"✅ accounts表: {cursor.fetchone()[0]}条")

        cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.positions")
        print(f"✅ positions表: {cursor.fetchone()[0]}条")

        cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.watchlist")
        print(f"✅ watchlist表: {cursor.fetchone()[0]}条")

        cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.position_history")
        print(f"✅ position_history表: {cursor.fetchone()[0]}条")

        print("\n🎉 数据迁移完成！")

    finally:
        conn.close()
