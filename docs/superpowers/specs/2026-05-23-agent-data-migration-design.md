# Agent数据迁移到PostgreSQL设计文档

**项目**: pi-investment 量化交易系统  
**版本**: v2.0  
**日期**: 2026-05-23  
**目的**: 将Agent的持仓、关注列表、交易历史、订单、现金数据从JSON文件迁移到PostgreSQL数据库

---

## 📋 目录

1. [项目背景](#项目背景)
2. [迁移范围](#迁移范围)
3. [数据库Schema设计](#数据库schema设计)
4. [数据映射关系](#数据映射关系)
5. [迁移脚本架构](#迁移脚本架构)
6. [后端API设计](#后端api设计)
7. [Agent代码集成](#agent代码集成)
8. [实施计划](#实施计划)
9. [验证清单](#验证清单)
10. [回滚方案](#回滚方案)

---

## 项目背景

### 当前状态

Agent数据存储在JSON文件中（`.pi-invest/`目录）：
- `portfolio.json` - 持仓数据（10个持仓）
- `watchlist.json` - 关注列表（30+个股票）
- `trades.json` - 交易历史（40+笔交易）
- `orders.json` - 订单数据（当前为空）
- `cash.json` - 现金余额

### 目标状态

- 所有数据迁移到PostgreSQL数据库
- 通过量化后端API访问数据
- JSON文件保留作为备份，不删除

### 迁移原则

1. **数据完整性**：所有JSON数据完整迁移，不丢失任何字段
2. **一次性迁移**：使用事务保护，失败可回滚
3. **保留备份**：JSON文件保持不变
4. **向后兼容**：迁移后Agent通过CLI/DAO访问数据

---

## 迁移范围

### 需要迁移的数据

| JSON文件 | 记录数 | 目标表 | 说明 |
|---------|--------|--------|------|
| portfolio.json | 10条 | positions | 当前持仓 |
| watchlist.json | 30+条 | watchlist | 关注列表 |
| trades.json | 40+条 | position_history | 交易历史 |
| orders.json | 0条 | orders | 订单（空） |
| cash.json | 1条 | accounts | 现金余额 |

### 不迁移的数据

- `backtest_report_*.json` - 回测报告（保留在文件系统）
- `FEISHU_CRON.json` - 飞书定时任务配置
- `fx-rates.json` - 汇率数据
- `portfolio.backup.*.json` - 备份文件

---

## 数据库Schema设计

### 1. 新增 `watchlist` 表

```sql
CREATE TABLE IF NOT EXISTS quant_agent.watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('A', 'HK', 'US')),
    buy_range_low DOUBLE PRECISION,
    buy_range_high DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    priority INTEGER DEFAULT 3,
    pool TEXT CHECK (pool IN ('A', 'B', 'C')),
    status TEXT DEFAULT 'watching' CHECK (status IN ('watching', 'paused', 'removed')),
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_watchlist_symbol ON quant_agent.watchlist(symbol);
CREATE INDEX idx_watchlist_priority ON quant_agent.watchlist(priority);
CREATE INDEX idx_watchlist_pool ON quant_agent.watchlist(pool);
CREATE INDEX idx_watchlist_status ON quant_agent.watchlist(status);
```

**字段说明**：
- `symbol`: 股票代码（唯一）
- `name`: 股票名称
- `market`: 市场（A股/港股/美股）
- `buy_range_low/high`: 买入价格区间
- `target_price`: 目标价
- `stop_loss`: 止损价
- `priority`: 优先级（1-4，1最高）
- `pool`: 股票池（A/B/C）
- `status`: 状态（watching/paused/removed）
- `reason`: 关注原因
- `notes`: 备注

### 2. 扩展 `positions` 表

```sql
ALTER TABLE quant_agent.positions 
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS market TEXT CHECK (market IN ('A', 'HK', 'US')),
ADD COLUMN IF NOT EXISTS sector TEXT,
ADD COLUMN IF NOT EXISTS notes TEXT,
ADD COLUMN IF NOT EXISTS original_cost DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS total_invested DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS batch_plan TEXT;
```

**新增字段说明**：
- `name`: 股票名称
- `market`: 市场
- `sector`: 行业板块
- `notes`: 持仓备注
- `original_cost`: 原始成本（首次建仓价格）
- `total_invested`: 总投入金额
- `batch_plan`: 分批计划

### 3. 扩展 `position_history` 表

```sql
ALTER TABLE quant_agent.position_history 
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS fee DOUBLE PRECISION DEFAULT 0,
ADD COLUMN IF NOT EXISTS realized_pnl DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS realized_pnl_pct DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS notes TEXT;
```

**新增字段说明**：
- `name`: 股票名称
- `fee`: 交易手续费
- `realized_pnl`: 已实现盈亏（卖出时）
- `realized_pnl_pct`: 已实现盈亏百分比
- `notes`: 交易备注

### 4. 扩展 `accounts` 表

```sql
ALTER TABLE quant_agent.accounts 
ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'CNY',
ADD COLUMN IF NOT EXISTS notes TEXT;
```

**新增字段说明**：
- `currency`: 货币类型（CNY/HKD/USD）
- `notes`: 账户备注

---

## 数据映射关系

### 1. portfolio.json → positions 表

| JSON字段 | PostgreSQL字段 | 说明 |
|---------|---------------|------|
| symbol | symbol | 股票代码 |
| name | name | 股票名称（新增） |
| quantity | quantity | 持仓数量 |
| avg_cost | cost_basis | 平均成本 |
| market | market | 市场（新增） |
| notes | notes | 备注（新增） |
| added_date | entry_date | 建仓日期 |
| original_cost | original_cost | 原始成本（新增） |
| total_invested | total_invested | 总投入（新增） |
| stop_loss | stop_loss | 止损价 |
| target_price | take_profit | 目标价 |
| batch_plan | batch_plan | 分批计划（新增） |
| sector | sector | 行业板块（新增） |
| buy_reason | entry_reason | 买入原因 |
| - | account_id | 固定为'default' |
| - | status | 固定为'open' |

**特殊处理**：
- 港股持仓：`avg_cost_hkd` 和 `purchase_fx_rate` 存入JSONB metadata字段
- `current_price`, `market_value`, `unrealized_pnl` 等实时数据在查询时计算

### 2. watchlist.json → watchlist 表

| JSON字段 | PostgreSQL字段 | 说明 |
|---------|---------------|------|
| symbol | symbol | 股票代码 |
| name | name | 股票名称 |
| market | market | 市场 |
| buy_range_low | buy_range_low | 买入区间下限 |
| buy_range_high | buy_range_high | 买入区间上限 |
| target_price | target_price | 目标价 |
| stop_loss | stop_loss | 止损价 |
| priority | priority | 优先级 |
| pool | pool | 股票池 |
| status | status | 状态 |
| reason | reason | 关注原因 |
| notes | notes | 备注 |
| created_at | created_at | 创建时间 |
| updated_at | updated_at | 更新时间 |

**数据完全一致，无需转换**

### 3. trades.json → position_history 表

| JSON字段 | PostgreSQL字段 | 说明 |
|---------|---------------|------|
| id | id | 交易ID（转UUID） |
| symbol | - | 用于查询position_id |
| name | name | 股票名称（新增） |
| action | action | 操作类型（buy/sell） |
| price | price | 成交价格 |
| quantity | quantity | 交易数量 |
| amount | amount | 交易金额 |
| fee | fee | 手续费（新增） |
| date | timestamp | 交易时间 |
| reason | reason | 交易原因 |
| pnl | realized_pnl | 已实现盈亏（新增） |
| pnl_pct | realized_pnl_pct | 盈亏百分比（新增） |
| notes | notes | 备注（新增） |
| - | position_id | 通过symbol关联positions表 |

**特殊处理**：
- `id` 从数字转换为UUID格式
- `position_id` 需要先查询positions表获取对应的UUID
- `date` 转换为TIMESTAMPTZ格式

### 4. orders.json → orders 表

**当前为空数组，无需迁移数据**

### 5. cash.json → accounts 表

| JSON字段 | PostgreSQL字段 | 说明 |
|---------|---------------|------|
| available_cash | current_capital | 可用资金 |
| currency | currency | 货币类型（新增） |
| notes | notes | 备注（新增） |
| last_updated | updated_at | 更新时间 |

**特殊处理**：
- 更新default账户（id='00000000-0000-0000-0000-000000000001'）
- 同时更新 `initial_capital` 为当前值（如果是首次设置）

---

## 迁移脚本架构

### 脚本位置

```
quant/scripts/migrate_agent_data_to_postgres.py
```

### 主要功能模块

#### 1. 配置模块

```python
class MigrationConfig:
    """迁移配置"""
    def __init__(self):
        self.pg_host = os.getenv('POSTGRES_HOST', 'localhost')
        self.pg_port = os.getenv('POSTGRES_PORT', '5432')
        self.pg_db = os.getenv('POSTGRES_DB', 'pi_investment')
        self.pg_user = os.getenv('POSTGRES_USER', 'postgres')
        self.pg_password = os.getenv('POSTGRES_PASSWORD')
        
        self.json_dir = Path('.pi-invest')
        self.portfolio_file = self.json_dir / 'portfolio.json'
        self.watchlist_file = self.json_dir / 'watchlist.json'
        self.trades_file = self.json_dir / 'trades.json'
        self.orders_file = self.json_dir / 'orders.json'
        self.cash_file = self.json_dir / 'cash.json'
```

#### 2. 数据加载模块

```python
class DataLoader:
    """JSON数据加载器"""
    
    def load_portfolio(self) -> List[Dict]:
        """加载持仓数据"""
        
    def load_watchlist(self) -> List[Dict]:
        """加载关注列表"""
        
    def load_trades(self) -> List[Dict]:
        """加载交易历史"""
        
    def load_cash(self) -> Dict:
        """加载现金数据"""
        
    def validate_data(self, data: Any, schema: str) -> bool:
        """验证数据格式"""
```

#### 3. Schema更新模块

```python
class SchemaUpdater:
    """数据库Schema更新器"""
    
    def create_watchlist_table(self, conn):
        """创建watchlist表"""
        
    def extend_positions_table(self, conn):
        """扩展positions表"""
        
    def extend_position_history_table(self, conn):
        """扩展position_history表"""
        
    def extend_accounts_table(self, conn):
        """扩展accounts表"""
        
    def verify_schema(self, conn) -> bool:
        """验证Schema更新成功"""
```

#### 4. 数据迁移模块

```python
class DataMigrator:
    """数据迁移器"""
    
    def migrate_accounts(self, conn, cash_data: Dict):
        """迁移账户数据"""
        
    def migrate_positions(self, conn, portfolio_data: List[Dict]) -> Dict[str, str]:
        """迁移持仓数据，返回symbol->position_id映射"""
        
    def migrate_watchlist(self, conn, watchlist_data: List[Dict]):
        """迁移关注列表"""
        
    def migrate_position_history(self, conn, trades_data: List[Dict], 
                                 symbol_to_position_id: Dict[str, str]):
        """迁移交易历史"""
        
    def generate_uuid_from_id(self, old_id: Union[int, str]) -> str:
        """从旧ID生成UUID"""
```

#### 5. 验证模块

```python
class DataValidator:
    """数据验证器"""
    
    def count_records(self, conn, table: str) -> int:
        """统计表记录数"""
        
    def verify_data_integrity(self, conn, original_data: Dict) -> bool:
        """验证数据完整性"""
        
    def generate_report(self, results: Dict) -> str:
        """生成迁移报告"""
```

### 执行流程

```python
def main():
    """主执行流程"""
    config = MigrationConfig()
    loader = DataLoader(config)
    
    # 1. 连接PostgreSQL
    conn = psycopg2.connect(...)
    
    try:
        # 2. 开启事务
        conn.autocommit = False
        
        # 3. 加载JSON数据
        portfolio_data = loader.load_portfolio()
        watchlist_data = loader.load_watchlist()
        trades_data = loader.load_trades()
        cash_data = loader.load_cash()
        
        # 4. 执行Schema更新
        schema_updater = SchemaUpdater()
        schema_updater.create_watchlist_table(conn)
        schema_updater.extend_positions_table(conn)
        schema_updater.extend_position_history_table(conn)
        schema_updater.extend_accounts_table(conn)
        
        # 5. 迁移数据
        migrator = DataMigrator()
        migrator.migrate_accounts(conn, cash_data)
        symbol_to_position_id = migrator.migrate_positions(conn, portfolio_data)
        migrator.migrate_watchlist(conn, watchlist_data)
        migrator.migrate_position_history(conn, trades_data, symbol_to_position_id)
        
        # 6. 验证数据
        validator = DataValidator()
        if validator.verify_data_integrity(conn, {
            'portfolio': portfolio_data,
            'watchlist': watchlist_data,
            'trades': trades_data
        }):
            # 7. 提交事务
            conn.commit()
            print("✅ 迁移成功")
        else:
            # 8. 回滚
            conn.rollback()
            print("❌ 数据验证失败，已回滚")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {e}")
        raise
    finally:
        conn.close()
```

### 特殊处理逻辑

#### UUID生成策略

```python
import uuid
import hashlib

def generate_uuid_from_id(old_id: Union[int, str]) -> str:
    """从旧ID生成确定性UUID"""
    # 使用MD5哈希生成UUID v5
    namespace = uuid.UUID('00000000-0000-0000-0000-000000000000')
    return str(uuid.uuid5(namespace, str(old_id)))
```

#### position_id关联

```python
def get_position_id_by_symbol(conn, symbol: str, account_id: str = 'default') -> str:
    """通过symbol查询position_id"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM quant_agent.positions 
        WHERE symbol = %s AND account_id = %s AND status = 'open'
    """, (symbol, account_id))
    result = cursor.fetchone()
    return result['id'] if result else None
```

#### 日期格式转换

```python
from dateutil import parser

def parse_date(date_str: str) -> datetime:
    """解析多种日期格式"""
    # 支持: "2026-05-23", "2026-05-23T10:30:00", "2026-05-23 10:30:00"
    return parser.parse(date_str)
```

---

## 后端API设计

### CLI命令规范

基于 `docs/backend-api-spec.md` 的规范，新增以下CLI命令组。

### 1. 持仓管理API

#### 获取持仓列表

```bash
quant position +list [--account-id default] [--status open] [--json]
```

**返回示例**：
```json
{
  "status": "success",
  "data": {
    "total": 10,
    "positions": [
      {
        "id": "uuid",
        "symbol": "000425",
        "name": "徐工机械",
        "quantity": 400,
        "cost_basis": 9.2,
        "market": "A",
        "sector": "工程机械",
        "entry_date": "2026-03-22",
        "entry_reason": "工程机械龙头，多次止盈后成本摊薄"
      }
    ]
  }
}
```

#### 获取单个持仓详情

```bash
quant position +get --symbol 600519 [--account-id default] [--json]
```

#### 更新持仓

```bash
quant position +update --symbol 600519 --quantity 100 --price 1850.00 [--json]
```

#### 关闭持仓

```bash
quant position +close --symbol 600519 --reason "止盈离场" [--json]
```

### 2. 关注列表API

#### 获取关注列表

```bash
quant watchlist +list [--pool A] [--status watching] [--json]
```

**返回示例**：
```json
{
  "status": "success",
  "data": {
    "total": 30,
    "items": [
      {
        "id": "uuid",
        "symbol": "002714",
        "name": "牧原股份",
        "market": "A",
        "buy_range_low": 42.0,
        "buy_range_high": 44.0,
        "target_price": 52.0,
        "stop_loss": 39.0,
        "priority": 2,
        "pool": "B",
        "status": "watching",
        "reason": "猪肉周期上行趋势确认"
      }
    ]
  }
}
```

#### 添加关注股票

```bash
quant watchlist +add --symbol 600519 --name 贵州茅台 \
  --buy-range-low 1800 --buy-range-high 1850 \
  --target-price 2000 --stop-loss 1750 \
  --priority 1 --pool A --reason "技术面突破" [--json]
```

#### 更新关注股票

```bash
quant watchlist +update --symbol 600519 \
  --buy-range-low 1820 --notes "等待回调" [--json]
```

#### 移除关注

```bash
quant watchlist +remove --symbol 600519 [--json]
```

### 3. 交易历史API

#### 获取交易历史

```bash
quant trades +list [--symbol 600519] [--start-date 2026-05-01] \
  [--end-date 2026-05-31] [--action buy] [--limit 50] [--json]
```

**返回示例**：
```json
{
  "status": "success",
  "data": {
    "total": 42,
    "trades": [
      {
        "id": "uuid",
        "symbol": "000425",
        "name": "徐工机械",
        "action": "buy",
        "price": 6.78,
        "quantity": 1500,
        "amount": 10170.0,
        "fee": 0.0,
        "timestamp": "2026-03-22T00:00:00Z",
        "reason": "工程机械龙头建仓"
      }
    ]
  }
}
```

#### 获取单笔交易详情

```bash
quant trades +get --trade-id <uuid> [--json]
```

#### 记录交易

```bash
quant trades +record --symbol 600519 --action buy \
  --quantity 100 --price 1850.00 --fee 5.0 \
  --reason "MACD金叉" [--json]
```

### 4. 账户管理API

#### 获取账户信息

```bash
quant account +info [--account-id default] [--json]
```

**返回示例**：
```json
{
  "status": "success",
  "data": {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Default Account",
    "account_type": "paper",
    "current_capital": 246363.7,
    "currency": "CNY",
    "notes": "可用资金余额，每次买卖后自动更新",
    "updated_at": "2026-05-14T05:26:55.296Z"
  }
}
```

#### 更新现金余额

```bash
quant account +update-cash --amount 246363.7 [--json]
```

#### 获取账户统计

```bash
quant account +stats [--account-id default] [--json]
```

**返回示例**：
```json
{
  "status": "success",
  "data": {
    "total_positions": 10,
    "total_market_value": 500000.0,
    "total_cash": 246363.7,
    "total_assets": 746363.7,
    "total_pnl": 46363.7,
    "total_pnl_pct": 6.62
  }
}
```

### 5. 订单管理API（已有，确认兼容）

```bash
# 创建订单
quant order +create --symbol 600519 --type buy \
  --quantity 100 --price 1850.00 --reason "买入信号" [--json]

# 获取订单列表
quant order +list [--status pending] [--json]
```

---

## Agent代码集成

### 代码结构

#### 1. 数据访问层（DAO）

```
quant/quantsys/db/dao/
├── __init__.py
├── base_dao.py          # 基础DAO类
├── position_dao.py      # 持仓数据访问
├── watchlist_dao.py     # 关注列表数据访问
├── trade_dao.py         # 交易历史数据访问
├── account_dao.py       # 账户数据访问
└── order_dao.py         # 订单数据访问
```

**base_dao.py 示例**：
```python
from typing import Optional, List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

class BaseDAO:
    """基础DAO类"""
    
    def __init__(self, connection=None):
        self.conn = connection or self._get_connection()
        
    def _get_connection(self):
        """获取数据库连接"""
        import os
        return psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'pi_investment'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD'),
            cursor_factory=RealDictCursor
        )
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """执行查询"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """执行更新"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor.rowcount
```

**position_dao.py 示例**：
```python
from .base_dao import BaseDAO
from typing import List, Dict, Optional

class PositionDAO(BaseDAO):
    """持仓数据访问对象"""
    
    def list_positions(self, account_id: str = 'default', 
                      status: str = 'open') -> List[Dict]:
        """获取持仓列表"""
        query = """
            SELECT * FROM quant_agent.positions
            WHERE account_id = %s AND status = %s
            ORDER BY entry_date DESC
        """
        return self.execute_query(query, (account_id, status))
    
    def get_position(self, symbol: str, account_id: str = 'default') -> Optional[Dict]:
        """获取单个持仓"""
        query = """
            SELECT * FROM quant_agent.positions
            WHERE symbol = %s AND account_id = %s AND status = 'open'
        """
        results = self.execute_query(query, (symbol, account_id))
        return results[0] if results else None
    
    def create_position(self, data: Dict) -> str:
        """创建持仓"""
        query = """
            INSERT INTO quant_agent.positions (
                account_id, symbol, name, market, quantity, cost_basis,
                entry_date, entry_reason, sector, notes, original_cost,
                total_invested, stop_loss, take_profit, batch_plan
            ) VALUES (
                %(account_id)s, %(symbol)s, %(name)s, %(market)s, %(quantity)s,
                %(cost_basis)s, %(entry_date)s, %(entry_reason)s, %(sector)s,
                %(notes)s, %(original_cost)s, %(total_invested)s, %(stop_loss)s,
                %(take_profit)s, %(batch_plan)s
            ) RETURNING id
        """
        cursor = self.conn.cursor()
        cursor.execute(query, data)
        self.conn.commit()
        return cursor.fetchone()['id']
    
    def update_position(self, symbol: str, data: Dict, 
                       account_id: str = 'default') -> int:
        """更新持仓"""
        set_clause = ', '.join([f"{k} = %({k})s" for k in data.keys()])
        query = f"""
            UPDATE quant_agent.positions
            SET {set_clause}, updated_at = now()
            WHERE symbol = %(symbol)s AND account_id = %(account_id)s
        """
        data['symbol'] = symbol
        data['account_id'] = account_id
        return self.execute_update(query, data)
    
    def close_position(self, symbol: str, account_id: str = 'default') -> int:
        """关闭持仓"""
        query = """
            UPDATE quant_agent.positions
            SET status = 'closed', updated_at = now()
            WHERE symbol = %s AND account_id = %s
        """
        return self.execute_update(query, (symbol, account_id))
```

#### 2. CLI命令层

```
quant/quantsys/cli/
├── position_management.py   # 持仓管理命令
├── watchlist_management.py  # 关注列表命令
├── trade_management.py      # 交易历史命令
└── account_management.py    # 账户管理命令
```

**position_management.py 示例**：
```python
import click
import json
from ..db.dao.position_dao import PositionDAO

@click.group(name='position')
def position_group():
    """持仓管理命令组"""
    pass

@position_group.command(name='+list')
@click.option('--account-id', default='default', help='账户ID')
@click.option('--status', default='open', help='持仓状态')
@click.option('--json', 'output_json', is_flag=True, help='JSON格式输出')
def list_positions(account_id, status, output_json):
    """获取持仓列表"""
    dao = PositionDAO()
    positions = dao.list_positions(account_id, status)
    
    if output_json:
        result = {
            "status": "success",
            "data": {
                "total": len(positions),
                "positions": positions
            }
        }
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for pos in positions:
            click.echo(f"{pos['symbol']} {pos['name']}: {pos['quantity']}股 @{pos['cost_basis']}")

@position_group.command(name='+get')
@click.option('--symbol', required=True, help='股票代码')
@click.option('--account-id', default='default', help='账户ID')
@click.option('--json', 'output_json', is_flag=True, help='JSON格式输出')
def get_position(symbol, account_id, output_json):
    """获取单个持仓详情"""
    dao = PositionDAO()
    position = dao.get_position(symbol, account_id)
    
    if output_json:
        result = {
            "status": "success" if position else "error",
            "data": position
        }
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if position:
            click.echo(f"持仓详情: {position}")
        else:
            click.echo(f"未找到持仓: {symbol}")

@position_group.command(name='+update')
@click.option('--symbol', required=True, help='股票代码')
@click.option('--quantity', type=int, help='持仓数量')
@click.option('--price', type=float, help='当前价格')
@click.option('--json', 'output_json', is_flag=True, help='JSON格式输出')
def update_position(symbol, quantity, price, output_json):
    """更新持仓"""
    dao = PositionDAO()
    data = {}
    if quantity is not None:
        data['quantity'] = quantity
    if price is not None:
        data['current_price'] = price
    
    rows = dao.update_position(symbol, data)
    
    if output_json:
        result = {
            "status": "success" if rows > 0 else "error",
            "data": {"updated_rows": rows}
        }
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        click.echo(f"更新成功: {rows}行")

@position_group.command(name='+close')
@click.option('--symbol', required=True, help='股票代码')
@click.option('--reason', help='关闭原因')
@click.option('--json', 'output_json', is_flag=True, help='JSON格式输出')
def close_position(symbol, reason, output_json):
    """关闭持仓"""
    dao = PositionDAO()
    rows = dao.close_position(symbol)
    
    if output_json:
        result = {
            "status": "success" if rows > 0 else "error",
            "data": {"closed": rows > 0, "reason": reason}
        }
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        click.echo(f"持仓已关闭: {symbol}")
```

#### 3. 集成到main.py

```python
# quant/quantsys/cli/main.py
from .position_management import position_group
from .watchlist_management import watchlist_group
from .trade_management import trades_group
from .account_management import account_group

@click.group()
def cli():
    """量化系统CLI"""
    pass

# 注册命令组
cli.add_command(position_group)
cli.add_command(watchlist_group)
cli.add_command(trades_group)
cli.add_command(account_group)
```

### Agent集成方式

#### 方式1：通过CLI调用（推荐）

```python
# Agent代码中
import subprocess
import json

def get_portfolio():
    """获取持仓列表"""
    result = subprocess.run(
        ['quant', 'position', '+list', '--json'],
        capture_output=True,
        text=True,
        check=True
    )
    data = json.loads(result.stdout)
    return data['data']['positions']

def add_to_watchlist(symbol, name, buy_low, buy_high, reason):
    """添加到关注列表"""
    result = subprocess.run([
        'quant', 'watchlist', '+add',
        '--symbol', symbol,
        '--name', name,
        '--buy-range-low', str(buy_low),
        '--buy-range-high', str(buy_high),
        '--reason', reason,
        '--json'
    ], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
```

#### 方式2：直接调用DAO（如果Agent在Python环境）

```python
# Agent代码中
from quantsys.db.dao.position_dao import PositionDAO
from quantsys.db.dao.watchlist_dao import WatchlistDAO

def get_portfolio():
    """获取持仓列表"""
    dao = PositionDAO()
    return dao.list_positions()

def add_to_watchlist(symbol, name, buy_low, buy_high, reason):
    """添加到关注列表"""
    dao = WatchlistDAO()
    return dao.add_watchlist({
        'symbol': symbol,
        'name': name,
        'buy_range_low': buy_low,
        'buy_range_high': buy_high,
        'reason': reason
    })
```

### 迁移策略

**阶段1：数据迁移**
- 执行迁移脚本
- JSON文件保持不变

**阶段2：双读模式（可选，用于验证）**
```python
def get_portfolio_safe():
    """安全获取持仓（带fallback）"""
    try:
        # 优先从PostgreSQL读取
        return get_portfolio_from_postgres()
    except Exception as e:
        logger.warning(f"PostgreSQL读取失败，fallback到JSON: {e}")
        return get_portfolio_from_json()
```

**阶段3：完全切换**
- Agent只使用PostgreSQL
- JSON文件作为备份保留

---

## 实施计划

### Step 1: Schema更新（1小时）

**任务**：
1. 创建migration脚本 `quant/quantsys/db/migrations/001_add_agent_data_tables.sql`
2. 包含所有CREATE TABLE和ALTER TABLE语句
3. 在开发环境执行并验证

**验证**：
```bash
# 验证表结构
psql -d pi_investment -c "\d quant_agent.watchlist"
psql -d pi_investment -c "\d quant_agent.positions"
psql -d pi_investment -c "\d quant_agent.position_history"
psql -d pi_investment -c "\d quant_agent.accounts"
```

### Step 2: 迁移脚本开发（3小时）

**任务**：
1. 创建 `quant/scripts/migrate_agent_data_to_postgres.py`
2. 实现所有模块（Config, Loader, SchemaUpdater, Migrator, Validator）
3. 添加详细日志和错误处理
4. 编写单元测试

**测试**：
```bash
# 使用测试数据验证
python quant/scripts/migrate_agent_data_to_postgres.py --dry-run
```

### Step 3: DAO层开发（4小时）

**任务**：
1. 实现5个DAO类
   - `position_dao.py` - 持仓CRUD
   - `watchlist_dao.py` - 关注列表CRUD
   - `trade_dao.py` - 交易历史CRUD
   - `account_dao.py` - 账户CRUD
   - `order_dao.py` - 订单CRUD（可能已存在）
2. 每个DAO提供标准方法（list, get, create, update, delete）
3. 单元测试覆盖

**测试**：
```bash
pytest quant/tests/test_dao_*.py -v
```

### Step 4: CLI命令开发（4小时）

**任务**：
1. 实现4组CLI命令
   - `position_management.py` - 持仓管理
   - `watchlist_management.py` - 关注列表管理
   - `trade_management.py` - 交易历史管理
   - `account_management.py` - 账户管理
2. 集成到 `main.py`
3. 命令行测试

**测试**：
```bash
quant position +list --json
quant watchlist +list --json
quant trades +list --json
quant account +info --json
```

### Step 5: 数据迁移执行（30分钟）

**任务**：
1. 备份JSON文件
2. 执行迁移脚本
3. 验证数据完整性
4. 生成迁移报告

**执行**：
```bash
# 1. 备份JSON文件
cp -r .pi-invest .pi-invest.backup.$(date +%Y%m%d)

# 2. 执行迁移
python quant/scripts/migrate_agent_data_to_postgres.py

# 3. 验证数据
quant position +list --json | jq '.data.total'  # 应该是10
quant watchlist +list --json | jq '.data.total'  # 应该是30+
quant trades +list --json | jq '.data.total'  # 应该是40+
```

### Step 6: Agent集成（2小时）

**任务**：
1. 修改Agent代码，调用新的CLI命令或DAO
2. 测试Agent读写功能
3. 验证业务逻辑正确性

**测试场景**：
- Agent读取持仓列表
- Agent添加关注股票
- Agent记录交易
- Agent更新现金余额

---

## 验证清单

### 数据完整性验证

- [ ] **positions表记录数** = portfolio.json中holdings数量（10条）
  ```sql
  SELECT COUNT(*) FROM quant_agent.positions WHERE status = 'open';
  ```

- [ ] **watchlist表记录数** = watchlist.json中items数量（30+条）
  ```sql
  SELECT COUNT(*) FROM quant_agent.watchlist WHERE status = 'watching';
  ```

- [ ] **position_history表记录数** = trades.json中trades数量（40+条）
  ```sql
  SELECT COUNT(*) FROM quant_agent.position_history;
  ```

- [ ] **accounts表的current_capital** = cash.json中available_cash（246363.7）
  ```sql
  SELECT current_capital FROM quant_agent.accounts WHERE name = 'Default Account';
  ```

- [ ] **关键字段值一致性**
  - 随机抽取5个持仓，对比symbol、name、quantity、cost_basis
  - 随机抽取5个关注股票，对比buy_range、target_price
  - 随机抽取5笔交易，对比price、quantity、amount

### 功能验证

- [ ] **CLI命令测试**
  - `quant position +list` 返回10个持仓
  - `quant position +get --symbol 000425` 返回徐工机械详情
  - `quant watchlist +list` 返回30+个关注股票
  - `quant watchlist +get --symbol 002714` 返回牧原股份详情
  - `quant trades +list` 返回40+笔交易
  - `quant trades +list --action buy` 只返回买入交易
  - `quant account +info` 返回正确的现金余额

- [ ] **Agent集成测试**
  - Agent能正常读取持仓数据
  - Agent能正常添加关注股票
  - Agent能正常记录交易
  - Agent能正常更新现金余额

### 性能验证

- [ ] **查询响应时间** < 100ms
  ```bash
  time quant position +list --json
  ```

- [ ] **批量插入性能** 满足需求
  - 插入30条watchlist记录 < 1秒

- [ ] **索引生效**
  ```sql
  EXPLAIN ANALYZE SELECT * FROM quant_agent.positions WHERE symbol = '000425';
  EXPLAIN ANALYZE SELECT * FROM quant_agent.watchlist WHERE pool = 'A';
  ```

### 数据一致性验证脚本

```python
# verify_migration.py
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def verify_portfolio():
    """验证持仓数据"""
    with open('.pi-invest/portfolio.json') as f:
        json_data = json.load(f)
    
    conn = psycopg2.connect(...)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM quant_agent.positions WHERE status = 'open'")
    db_data = cursor.fetchall()
    
    assert len(json_data['holdings']) == len(db_data), "持仓数量不一致"
    
    for json_pos in json_data['holdings']:
        db_pos = next((p for p in db_data if p['symbol'] == json_pos['symbol']), None)
        assert db_pos is not None, f"持仓{json_pos['symbol']}未找到"
        assert db_pos['quantity'] == json_pos['quantity'], f"数量不一致: {json_pos['symbol']}"
        assert abs(db_pos['cost_basis'] - json_pos['avg_cost']) < 0.01, f"成本不一致: {json_pos['symbol']}"
    
    print("✅ 持仓数据验证通过")

def verify_watchlist():
    """验证关注列表"""
    with open('.pi-invest/watchlist.json') as f:
        json_data = json.load(f)
    
    conn = psycopg2.connect(...)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM quant_agent.watchlist")
    db_data = cursor.fetchall()
    
    assert len(json_data['items']) == len(db_data), "关注列表数量不一致"
    print("✅ 关注列表验证通过")

def verify_trades():
    """验证交易历史"""
    with open('.pi-invest/trades.json') as f:
        json_data = json.load(f)
    
    conn = psycopg2.connect(...)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM quant_agent.position_history")
    db_data = cursor.fetchall()
    
    assert len(json_data['trades']) == len(db_data), "交易历史数量不一致"
    print("✅ 交易历史验证通过")

if __name__ == '__main__':
    verify_portfolio()
    verify_watchlist()
    verify_trades()
    print("\n🎉 所有数据验证通过！")
```

---

## 回滚方案

### 场景1：迁移脚本执行失败

**现象**：迁移过程中抛出异常

**处理**：
- 事务自动回滚，PostgreSQL数据未改变
- JSON文件未修改，Agent继续使用JSON
- 修复问题后重新执行迁移

### 场景2：数据验证失败

**现象**：迁移完成但数据不一致

**处理**：
```sql
-- 清空迁移的数据
DELETE FROM quant_agent.position_history;
DELETE FROM quant_agent.positions WHERE account_id = 'default';
DELETE FROM quant_agent.watchlist;
UPDATE quant_agent.accounts SET current_capital = 100000.0 WHERE name = 'Default Account';
```

- Agent继续使用JSON文件
- 分析问题原因，修复后重新迁移

### 场景3：Agent集成后发现问题

**现象**：Agent读写PostgreSQL出现错误

**处理**：
- 临时切换Agent回JSON模式
- 修复DAO或CLI命令问题
- 重新测试后再切换回PostgreSQL

### 数据恢复

如果需要从备份恢复JSON文件：
```bash
cp -r .pi-invest.backup.20260523/* .pi-invest/
```

---

## 文档输出

### 1. 设计文档

- **文件**: `docs/superpowers/specs/2026-05-23-agent-data-migration-design.md`
- **内容**: 本文档

### 2. 迁移报告（迁移后生成）

- **文件**: `docs/migration-report-20260523.md`
- **内容**:
  - 迁移执行时间
  - 迁移数据统计
  - 验证结果
  - 遇到的问题和解决方案

### 3. API文档更新

- **文件**: `docs/backend-api-spec.md`
- **更新内容**:
  - 新增持仓管理API章节
  - 新增关注列表API章节
  - 新增交易历史API章节
  - 新增账户管理API章节

---

## 总结

### 迁移范围

- **5个JSON文件** → **4个PostgreSQL表**
- **新增1个表**（watchlist）
- **扩展4个表**（positions, position_history, accounts, orders）
- **开发完整的DAO层和CLI API**
- **Agent代码集成**

### 核心原则

1. **数据完整性**：所有字段完整迁移
2. **一次性迁移**：事务保护，失败回滚
3. **保留备份**：JSON文件不删除
4. **向后兼容**：通过CLI/DAO访问数据

### 预估工时

| 任务 | 工时 |
|-----|------|
| Schema更新 | 1小时 |
| 迁移脚本开发 | 3小时 |
| DAO层开发 | 4小时 |
| CLI命令开发 | 4小时 |
| 数据迁移执行 | 0.5小时 |
| Agent集成 | 2小时 |
| **总计** | **14.5小时** |

### 风险控制

- ✅ 事务保护，失败自动回滚
- ✅ JSON文件保留，可随时恢复
- ✅ 完整的验证清单
- ✅ 清晰的回滚方案
- ✅ 分阶段实施，可逐步验证

---

**文档版本**: v1.0  
**最后更新**: 2026-05-23  
**作者**: Kiro AI Assistant
