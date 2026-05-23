# Agent 数据 DAO 层和 CLI 命令实现设计

> 设计日期：2026-05-23
> 基于：已完成的 PostgreSQL 数据迁移

## 目标

为已迁移到 PostgreSQL 的 Agent 数据（持仓、关注列表、交易历史、账户）实现完整的数据访问层（DAO）和 CLI 命令接口，使 Agent 能够通过编程方式访问和管理这些数据。

## 背景

- ✅ PostgreSQL 迁移已完成（10个持仓、29个关注列表、17笔交易）
- ✅ 数据存储在 `quant_agent` schema 中
- ✅ 项目使用 CommandRegistry 系统构建 CLI
- ✅ 现有数据库连接通过 `quantsys/data/db.Database` 类管理

## 架构设计

### 整体架构

```
用户/Agent
    ↓
CLI 命令 (main.py CommandRegistry)
    ↓
Handler 函数
    ↓
DAO 层 (db/dao/)
    ↓
Database 类 (data/db.py)
    ↓
PostgreSQL (quant_agent schema)
```

### 技术选型

- **数据库连接**：复用 `quantsys/data/db.Database` 类
- **CLI 框架**：CommandRegistry（现有系统）
- **命名格式**：`domain.action`（如 `position.list`）
- **调用格式**：`quant domain +action --params`
- **输出格式**：统一 JSON 格式

## DAO 层设计

### 目录结构

```
quant/quantsys/db/dao/
├── __init__.py
├── base_dao.py          # 基础 DAO 类
├── position_dao.py      # 持仓数据访问
├── watchlist_dao.py     # 关注列表数据访问
├── trade_dao.py         # 交易历史数据访问
└── account_dao.py       # 账户数据访问
```

### BaseDAO 设计

**职责**：
- 提供数据库连接管理
- 提供通用查询/更新方法
- 自动处理 schema 前缀
- 统一错误处理

**核心方法**：
- `__init__(db=None)` - 接受外部 Database 实例或创建新实例
- `execute_query(query, params)` - 执行查询，返回结果列表
- `execute_update(query, params)` - 执行更新，返回影响行数
- `execute_insert(query, params)` - 执行插入，返回新记录 ID

**特性**：
- 自动添加 `quant_agent.` schema 前缀
- 使用 RealDictCursor 返回字典格式结果
- 支持事务管理

### PositionDAO 设计

**方法列表**：

1. `list_positions(account_id='default', status='open')` → List[Dict]
   - 获取持仓列表
   - 按 entry_date 降序排序
   - 返回所有持仓字段

2. `get_position(symbol, account_id='default')` → Optional[Dict]
   - 获取单个持仓详情
   - 只返回 open 状态的持仓
   - 不存在返回 None

3. `update_position(symbol, data, account_id='default')` → int
   - 更新持仓信息
   - data 可包含：quantity, current_price, stop_loss, take_profit, notes
   - 返回更新的行数

4. `close_position(symbol, reason=None, account_id='default')` → int
   - 关闭持仓（设置 status='closed'）
   - 可选记录关闭原因
   - 返回更新的行数

5. `get_position_summary(account_id='default')` → Dict
   - 获取持仓汇总统计
   - 返回：总持仓数、总市值、总成本、总盈亏等

### WatchlistDAO 设计

**方法列表**：

1. `list_watchlist(pool=None, priority=None, status='watching')` → List[Dict]
   - 获取关注列表
   - 支持按 pool、priority、status 过滤
   - 按 priority 升序、symbol 升序排序

2. `get_watchlist_item(symbol)` → Optional[Dict]
   - 获取单个关注项详情
   - 不存在返回 None

3. `add_to_watchlist(data)` → str
   - 添加到关注列表
   - data 必须包含：symbol, name, market
   - 可选：priority, pool, buy_range_low, buy_range_high, target_price, stop_loss, reason, notes
   - 返回新记录的 UUID

4. `remove_from_watchlist(symbol)` → int
   - 从关注列表移除（物理删除）
   - 返回删除的行数

5. `update_watchlist_item(symbol, data)` → int
   - 更新关注项
   - data 可包含：priority, pool, status, buy_range_low, buy_range_high, target_price, stop_loss, reason, notes
   - 返回更新的行数

### TradeDAO 设计

**方法列表**：

1. `list_trades(symbol=None, start_date=None, end_date=None, limit=100)` → List[Dict]
   - 获取交易历史
   - 支持按 symbol、日期范围过滤
   - 按 timestamp 降序排序
   - 默认限制 100 条

2. `get_trade(trade_id)` → Optional[Dict]
   - 获取单笔交易详情
   - 通过 notes 字段中的 trade_id 查找
   - 不存在返回 None

3. `get_trade_stats(symbol=None, period='all')` → Dict
   - 获取交易统计
   - period: 'all', 'year', 'month', 'week'
   - 返回：总交易次数、总盈亏、胜率、平均盈亏等

### AccountDAO 设计

**方法列表**：

1. `get_account(name='Default Account')` → Optional[Dict]
   - 获取账户信息
   - 返回账户余额、货币等信息

2. `update_account(name, data)` → int
   - 更新账户信息
   - data 可包含：current_capital, currency, notes
   - 返回更新的行数

## CLI 命令设计

### 命令注册格式

所有命令注册到 `main.py` 的 `build_registry()` 函数中，使用 `CommandSpec` 格式：

```python
registry.register(
    CommandSpec(
        name="position.list",
        domain="position",
        action="list",
        description="List all positions",
        params={
            "account_id": {"type": "string", "required": False, "default": "default"},
            "status": {"type": "string", "required": False, "default": "open"}
        },
        examples=["quant position +list --json"],
        handler=_handle_position_list,
    )
)
```

### Position 命令组

**1. position.list**
- 描述：列出持仓
- 参数：account_id (可选), status (可选)
- 示例：`quant position +list --json`
- 输出：持仓列表（symbol, name, quantity, cost_basis, entry_date 等）

**2. position.get**
- 描述：获取单个持仓详情
- 参数：symbol (必需), account_id (可选)
- 示例：`quant position +get --symbol 600036 --json`
- 输出：完整持仓信息

**3. position.update**
- 描述：更新持仓
- 参数：symbol (必需), quantity (可选), price (可选), stop_loss (可选), take_profit (可选)
- 示例：`quant position +update --symbol 600036 --price 38.5 --json`
- 输出：更新结果

**4. position.close**
- 描述：关闭持仓
- 参数：symbol (必需), reason (可选)
- 示例：`quant position +close --symbol 600036 --reason "止盈" --json`
- 输出：关闭结果

**5. position.summary**
- 描述：持仓汇总统计
- 参数：account_id (可选)
- 示例：`quant position +summary --json`
- 输出：总持仓数、总市值、总成本、总盈亏等

### Watchlist 命令组

**1. watchlist.list**
- 描述：列出关注列表
- 参数：pool (可选), priority (可选), status (可选)
- 示例：`quant watchlist +list --pool A --priority 1 --json`
- 输出：关注列表

**2. watchlist.get**
- 描述：获取关注项详情
- 参数：symbol (必需)
- 示例：`quant watchlist +get --symbol 002025 --json`
- 输出：完整关注项信息

**3. watchlist.add**
- 描述：添加到关注列表
- 参数：symbol (必需), name (必需), market (必需), priority (可选), pool (可选), buy_range_low (可选), buy_range_high (可选), target_price (可选), stop_loss (可选), reason (可选)
- 示例：`quant watchlist +add --symbol 600519 --name 贵州茅台 --market A --priority 1 --json`
- 输出：新记录 ID

**4. watchlist.remove**
- 描述：移除关注
- 参数：symbol (必需)
- 示例：`quant watchlist +remove --symbol 600519 --json`
- 输出：删除结果

**5. watchlist.update**
- 描述：更新关注项
- 参数：symbol (必需), priority (可选), pool (可选), status (可选), buy_range_low (可选), buy_range_high (可选), target_price (可选), stop_loss (可选), reason (可选)
- 示例：`quant watchlist +update --symbol 600519 --priority 2 --json`
- 输出：更新结果

### Trade 命令组

**1. trade.list**
- 描述：列出交易历史
- 参数：symbol (可选), start_date (可选), end_date (可选), limit (可选)
- 示例：`quant trade +list --symbol 600036 --limit 10 --json`
- 输出：交易历史列表

**2. trade.get**
- 描述：获取单笔交易
- 参数：trade_id (必需)
- 示例：`quant trade +get --trade_id 1600000001001 --json`
- 输出：交易详情

**3. trade.stats**
- 描述：交易统计
- 参数：symbol (可选), period (可选，默认 'all')
- 示例：`quant trade +stats --symbol 600036 --period month --json`
- 输出：交易统计（总次数、总盈亏、胜率等）

### Account 命令组

**1. account.get**
- 描述：获取账户信息
- 参数：name (可选，默认 'Default Account')
- 示例：`quant account +get --json`
- 输出：账户余额、货币等

**2. account.update**
- 描述：更新账户
- 参数：name (可选), capital (可选), currency (可选)
- 示例：`quant account +update --capital 250000 --json`
- 输出：更新结果

## 数据流设计

### 请求流程

```
1. 用户执行命令：quant position +list --json
2. main.py 解析参数
3. CommandRegistry 路由到 _handle_position_list
4. Handler 创建 PositionDAO 实例
5. 调用 dao.list_positions()
6. DAO 通过 Database 执行 SQL
7. PostgreSQL 返回结果
8. DAO 格式化为字典列表
9. Handler 包装为标准 JSON 格式
10. 输出到终端
```

### 响应格式

**成功响应**：
```json
{
  "status": "success",
  "data": {
    "total": 10,
    "positions": [
      {
        "id": "uuid",
        "symbol": "600036",
        "name": "招商银行",
        "quantity": 300,
        "cost_basis": 37.89,
        "entry_date": "2026-05-13",
        ...
      }
    ]
  }
}
```

**错误响应**：
```json
{
  "status": "error",
  "message": "数据库连接失败",
  "code": "DB_CONNECTION_ERROR"
}
```

## 错误处理

### DAO 层错误

**数据库连接错误**：
- 场景：PostgreSQL 连接失败
- 处理：抛出 `DatabaseConnectionError`
- 消息：包含连接参数（隐藏密码）

**SQL 执行错误**：
- 场景：SQL 语法错误、约束违反等
- 处理：抛出 `DatabaseQueryError`
- 消息：包含 SQL 语句和错误详情

**数据不存在**：
- 场景：查询不到记录
- 处理：返回 `None` 或空列表（不抛异常）
- 原因：这是正常业务场景

### CLI 层错误

**参数验证错误**：
- 场景：必需参数缺失、类型错误
- 处理：返回 error 状态的 JSON
- 消息：明确指出哪个参数有问题

**DAO 异常**：
- 场景：DAO 层抛出异常
- 处理：捕获并转换为 error JSON
- 消息：用户友好的错误描述

**业务逻辑错误**：
- 场景：如关闭不存在的持仓
- 处理：返回 error 状态的 JSON
- 消息：具体的业务错误信息

### 错误码定义

- `DB_CONNECTION_ERROR` - 数据库连接失败
- `DB_QUERY_ERROR` - SQL 执行失败
- `INVALID_PARAMS` - 参数验证失败
- `NOT_FOUND` - 记录不存在
- `DUPLICATE_ENTRY` - 重复记录
- `BUSINESS_ERROR` - 业务逻辑错误

## 事务管理

### 读操作
- 不需要显式事务
- 使用默认的自动提交模式

### 单个写操作
- 自动提交
- DAO 方法内部调用 `conn.commit()`

### 多个写操作
- 使用事务包装
- 示例：批量更新持仓时使用 `with conn.transaction()`

## 性能优化

### 查询优化

**分页支持**：
- 所有列表查询支持 limit/offset
- 默认 limit=100，防止大结果集

**索引利用**：
- 已在 migration 中创建的索引：
  - positions: account_id, symbol, status, entry_date
  - watchlist: symbol, priority, pool, status
  - position_history: symbol, timestamp

**查询字段选择**：
- 列表查询只返回必要字段
- 详情查询返回完整字段

### 连接管理

**连接复用**：
- DAO 支持接受外部 Database 实例
- 批量操作时复用同一连接

**连接池**：
- 依赖 Database 类的连接管理
- 不在 DAO 层实现连接池

## 测试策略

### 单元测试

**DAO 层测试**：
- 使用测试数据库
- 每个 DAO 方法独立测试
- 测试正常流程和异常情况

**CLI 层测试**：
- Mock DAO 层
- 测试参数解析和输出格式
- 测试错误处理

### 集成测试

**端到端测试**：
- 使用真实 PostgreSQL 数据库
- 测试完整的命令执行流程
- 验证数据一致性

## 实施计划

### 阶段 1：DAO 层开发（预计 4 小时）

1. 实现 BaseDAO（1 小时）
2. 实现 PositionDAO（1 小时）
3. 实现 WatchlistDAO（1 小时）
4. 实现 TradeDAO 和 AccountDAO（1 小时）

### 阶段 2：CLI 命令开发（预计 4 小时）

1. 实现 Position 命令组（1.5 小时）
2. 实现 Watchlist 命令组（1.5 小时）
3. 实现 Trade 和 Account 命令组（1 小时）

### 阶段 3：测试和文档（预计 2 小时）

1. 编写单元测试（1 小时）
2. 集成测试和调试（0.5 小时）
3. 更新文档（0.5 小时）

## 向后兼容性

### 现有代码影响

- ✅ 不影响现有 CLI 命令
- ✅ 不修改现有数据库表结构
- ✅ 新增的 DAO 和命令是独立的

### 迁移路径

- Agent 可以逐步从 JSON 文件切换到 PostgreSQL
- 两种方式可以并存
- JSON 文件保留作为备份

## 安全考虑

### SQL 注入防护

- 所有 SQL 使用参数化查询
- 不拼接用户输入到 SQL 语句

### 权限控制

- 依赖 PostgreSQL 的用户权限
- DAO 层不实现额外的权限检查

### 数据验证

- CLI 层验证参数类型和范围
- DAO 层验证业务规则（如数量 > 0）

## 附录

### 数据库 Schema 参考

```sql
-- positions 表
CREATE TABLE quant_agent.positions (
    id UUID PRIMARY KEY,
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    market TEXT,
    quantity INTEGER NOT NULL,
    cost_basis DOUBLE PRECISION NOT NULL,
    entry_date DATE NOT NULL,
    entry_reason TEXT,
    sector TEXT,
    notes TEXT,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    status TEXT DEFAULT 'open',
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- watchlist 表
CREATE TABLE quant_agent.watchlist (
    id UUID PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    buy_range_low DOUBLE PRECISION,
    buy_range_high DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    priority INTEGER DEFAULT 3,
    pool TEXT,
    status TEXT DEFAULT 'watching',
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- position_history 表
CREATE TABLE quant_agent.position_history (
    id UUID PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION DEFAULT 0,
    realized_pnl DOUBLE PRECISION,
    realized_pnl_pct DOUBLE PRECISION,
    timestamp TIMESTAMPTZ NOT NULL,
    notes TEXT
);

-- accounts 表
CREATE TABLE quant_agent.accounts (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    current_capital DOUBLE PRECISION NOT NULL,
    currency TEXT DEFAULT 'CNY',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 环境变量配置

```bash
# PostgreSQL 连接（项目已配置）
QUANT_DB_PROVIDER=postgres
PGDATABASE=quant_investment

# 可选：使用 DSN 格式
# DATABASE_URL=postgresql://user:pass@localhost:5432/quant_investment
```

### 示例用法

```bash
# 查看持仓
quant position +list --json

# 获取单个持仓
quant position +get --symbol 600036 --json

# 更新持仓价格
quant position +update --symbol 600036 --price 38.5 --json

# 添加到关注列表
quant watchlist +add --symbol 600519 --name 贵州茅台 --market A --priority 1 --json

# 查看交易历史
quant trade +list --symbol 600036 --limit 10 --json

# 获取账户信息
quant account +get --json
```
