# 数据库设计文档

**项目**: pi-investment 量化交易系统  
**版本**: v2.0  
**日期**: 2026-05-22  
**数据库**: SQLite (开发) / PostgreSQL (生产)

---

## 📋 目录

1. [表结构设计](#表结构设计)
2. [索引设计](#索引设计)
3. [数据关系图](#数据关系图)
4. [数据字典](#数据字典)

---

## 表结构设计

### 1. agent_logs（Agent操作日志）

**用途**: 记录Agent的每个操作，用于展示"Agent做了什么"

```sql
CREATE TABLE agent_logs (
    log_id VARCHAR(50) PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    action_type VARCHAR(20) NOT NULL,
    symbol VARCHAR(10),
    details TEXT,
    result TEXT,
    metadata TEXT,
    status VARCHAR(20) DEFAULT 'success',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_timestamp (timestamp),
    INDEX idx_symbol (symbol),
    INDEX idx_action_type (action_type),
    INDEX idx_status (status)
);
```

**字段说明**:
- `log_id`: 日志唯一ID，格式 `log_YYYYMMDD_HHMMSS_NNN`
- `timestamp`: 操作时间
- `action_type`: 操作类型 - `scan`, `analyze`, `signal`, `trade`, `monitor`
- `symbol`: 股票代码（可选）
- `details`: 操作详情（JSON格式）
- `result`: 操作结果（JSON格式）
- `metadata`: 元数据（API调用、耗时等，JSON格式）
- `status`: 状态 - `success`, `failed`, `pending`

**示例数据**:
```sql
INSERT INTO agent_logs VALUES (
    'log_20260522_104530_001',
    '2026-05-22 10:45:30',
    'analyze',
    '600519',
    '{"modules":["technical","fundamental","fund_flow"]}',
    '{"score":80,"decision":"buy","confidence":0.85}',
    '{"api_calls":[{"api":"calculate_technical_indicators","duration_ms":234}]}',
    'success',
    '2026-05-22 10:45:30'
);
```

---

### 2. positions（持仓）

**用途**: 管理当前持仓，支持多账户

```sql
CREATE TABLE positions (
    position_id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL DEFAULT 'default',
    symbol VARCHAR(10) NOT NULL,
    name VARCHAR(50),
    shares INT NOT NULL,
    cost DECIMAL(10, 2) NOT NULL,
    current_price DECIMAL(10, 2),
    market_value DECIMAL(12, 2),
    pnl DECIMAL(12, 2),
    pnl_pct DECIMAL(6, 2),
    weight DECIMAL(5, 4),
    stop_loss DECIMAL(10, 2),
    target_price DECIMAL(10, 2),
    entry_date DATE NOT NULL,
    entry_reason TEXT,
    operated_by VARCHAR(20) DEFAULT 'agent',
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE INDEX idx_account_symbol (account_id, symbol),
    INDEX idx_status (status),
    INDEX idx_entry_date (entry_date)
);
```

**字段说明**:
- `position_id`: 持仓唯一ID
- `account_id`: 账户ID，支持多账户
- `symbol`: 股票代码
- `name`: 股票名称
- `shares`: 持有股数
- `cost`: 成本价
- `current_price`: 当前价（实时更新）
- `market_value`: 市值
- `pnl`: 盈亏金额
- `pnl_pct`: 盈亏百分比
- `weight`: 仓位占比
- `stop_loss`: 止损价
- `target_price`: 目标价
- `entry_date`: 建仓日期
- `entry_reason`: 建仓原因
- `operated_by`: 操作者 - `agent`, `user`
- `status`: 状态 - `active`, `closed`

**示例数据**:
```sql
INSERT INTO positions VALUES (
    'pos_20260515_001',
    'default',
    '600519',
    '贵州茅台',
    100,
    1600.00,
    1850.00,
    185000.00,
    25000.00,
    15.60,
    0.2000,
    1750.00,
    1950.00,
    '2026-05-15',
    '技术面超卖+基本面优质',
    'agent',
    'active',
    '2026-05-15 10:30:00',
    '2026-05-22 14:30:00'
);
```

---

### 3. position_history（持仓历史）

**用途**: 记录持仓的每次变动

```sql
CREATE TABLE position_history (
    history_id VARCHAR(50) PRIMARY KEY,
    position_id VARCHAR(50) NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    action VARCHAR(20) NOT NULL,
    shares INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    operated_by VARCHAR(20) NOT NULL,
    reason TEXT,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_position_id (position_id),
    INDEX idx_symbol (symbol),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (position_id) REFERENCES positions(position_id)
);
```

**字段说明**:
- `history_id`: 历史记录ID
- `position_id`: 关联的持仓ID
- `action`: 操作类型 - `buy`, `sell`, `adjust_stop_loss`, `adjust_target`
- `shares`: 股数
- `price`: 价格
- `amount`: 金额
- `operated_by`: 操作者
- `reason`: 原因
- `timestamp`: 操作时间

---

### 4. orders（订单）

**用途**: 管理交易订单，支持审批流程

```sql
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL DEFAULT 'default',
    symbol VARCHAR(10) NOT NULL,
    name VARCHAR(50),
    action VARCHAR(10) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    shares INT NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    order_type VARCHAR(20) DEFAULT 'limit',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    submitted_by VARCHAR(20) NOT NULL,
    submitted_at DATETIME NOT NULL,
    approved_by VARCHAR(50),
    approved_at DATETIME,
    rejected_by VARCHAR(50),
    rejected_at DATETIME,
    executed_at DATETIME,
    execution_price DECIMAL(10, 2),
    slippage DECIMAL(10, 2),
    commission DECIMAL(10, 2),
    reason TEXT,
    feedback TEXT,
    analysis_log_id VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status (status),
    INDEX idx_symbol (symbol),
    INDEX idx_submitted_at (submitted_at),
    INDEX idx_account_id (account_id),
    FOREIGN KEY (analysis_log_id) REFERENCES agent_logs(log_id)
);
```

**字段说明**:
- `order_id`: 订单唯一ID
- `action`: 操作类型 - `buy`, `sell`
- `order_type`: 订单类型 - `limit`, `market`
- `status`: 状态 - `pending`, `approved`, `rejected`, `executed`, `cancelled`
- `submitted_by`: 提交者 - `agent`, `user`
- `approved_by`: 审批人
- `rejected_by`: 拒绝人
- `execution_price`: 实际成交价
- `slippage`: 滑点
- `commission`: 手续费
- `reason`: 提交原因
- `feedback`: 审批反馈
- `analysis_log_id`: 关联的分析日志ID

**示例数据**:
```sql
INSERT INTO orders VALUES (
    'order_20260522_104530_001',
    'default',
    '600519',
    '贵州茅台',
    'buy',
    1820.00,
    100,
    182000.00,
    'limit',
    'pending',
    'agent',
    '2026-05-22 10:45:30',
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    '技术面超卖+基本面优质',
    NULL,
    'log_20260522_104530_001',
    '2026-05-22 10:45:30',
    '2026-05-22 10:45:30'
);
```

---

### 5. agent_decisions（Agent决策记录）

**用途**: 记录Agent的每个决策，用于绩效统计和学习

```sql
CREATE TABLE agent_decisions (
    decision_id VARCHAR(50) PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    name VARCHAR(50),
    decision VARCHAR(10) NOT NULL,
    confidence DECIMAL(3, 2) NOT NULL,
    timestamp DATETIME NOT NULL,
    analysis_log_id VARCHAR(50),
    reasoning TEXT,
    technical_score INT,
    fundamental_score INT,
    overall_score INT,
    buy_range_low DECIMAL(10, 2),
    buy_range_high DECIMAL(10, 2),
    stop_loss DECIMAL(10, 2),
    target_price DECIMAL(10, 2),
    feedback VARCHAR(20),
    user_comment TEXT,
    actual_result TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_symbol (symbol),
    INDEX idx_timestamp (timestamp),
    INDEX idx_feedback (feedback),
    INDEX idx_decision (decision),
    FOREIGN KEY (analysis_log_id) REFERENCES agent_logs(log_id)
);
```

**字段说明**:
- `decision_id`: 决策唯一ID
- `decision`: 决策类型 - `buy`, `sell`, `hold`
- `confidence`: 置信度 (0-1)
- `analysis_log_id`: 关联的分析日志ID
- `reasoning`: 推理过程（JSON格式）
- `technical_score`: 技术面评分
- `fundamental_score`: 基本面评分
- `overall_score`: 综合评分
- `feedback`: 反馈 - `correct`, `wrong`, `partial`, `pending`
- `user_comment`: 用户评论
- `actual_result`: 实际结果（JSON格式，包含实际收益等）

---

### 6. data_snapshots（数据快照）

**用途**: 保存历史数据快照，用于复现分析

```sql
CREATE TABLE data_snapshots (
    snapshot_id VARCHAR(50) PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    timestamp DATETIME NOT NULL,
    data TEXT NOT NULL,
    size_bytes INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_symbol_timestamp (symbol, timestamp),
    INDEX idx_data_type (data_type),
    INDEX idx_timestamp (timestamp)
);
```

**字段说明**:
- `snapshot_id`: 快照唯一ID
- `data_type`: 数据类型 - `quote`, `kline`, `financial`, `fund_flow`, `technical`
- `data`: 数据内容（JSON格式）
- `size_bytes`: 数据大小（字节）

**示例数据**:
```sql
INSERT INTO data_snapshots VALUES (
    'snapshot_20260522_104530_001',
    '600519',
    'quote',
    '2026-05-22 10:45:30',
    '{"price":1850,"change_pct":2.5,"volume":12000000}',
    58,
    '2026-05-22 10:45:30'
);
```

---

### 7. approval_rules（审批规则）

**用途**: 配置审批规则

```sql
CREATE TABLE approval_rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    condition TEXT NOT NULL,
    action VARCHAR(50) NOT NULL,
    approver VARCHAR(50) NOT NULL,
    priority INT DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_enabled (enabled),
    INDEX idx_priority (priority)
);
```

**字段说明**:
- `rule_id`: 规则ID
- `rule_name`: 规则名称
- `condition`: 条件表达式（如 `order_amount > 100000`）
- `action`: 动作 - `require_approval`, `auto_approve`, `auto_reject`
- `approver`: 审批人
- `priority`: 优先级（数字越大优先级越高）
- `enabled`: 是否启用

**示例数据**:
```sql
INSERT INTO approval_rules VALUES (
    'rule_001',
    '大额订单需审批',
    'order_amount > 100000',
    'require_approval',
    'user',
    10,
    TRUE,
    '2026-05-22 10:00:00',
    '2026-05-22 10:00:00'
);
```

---

### 8. accounts（账户）

**用途**: 管理多个交易账户

```sql
CREATE TABLE accounts (
    account_id VARCHAR(50) PRIMARY KEY,
    account_name VARCHAR(100) NOT NULL,
    initial_capital DECIMAL(12, 2) NOT NULL,
    current_capital DECIMAL(12, 2) NOT NULL,
    cash DECIMAL(12, 2) NOT NULL,
    market_value DECIMAL(12, 2) NOT NULL,
    total_value DECIMAL(12, 2) NOT NULL,
    total_pnl DECIMAL(12, 2) NOT NULL,
    total_pnl_pct DECIMAL(6, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status (status)
);
```

**字段说明**:
- `account_id`: 账户ID
- `account_name`: 账户名称
- `initial_capital`: 初始资金
- `current_capital`: 当前资金
- `cash`: 现金
- `market_value`: 持仓市值
- `total_value`: 总资产
- `total_pnl`: 总盈亏
- `total_pnl_pct`: 总盈亏百分比
- `status`: 状态 - `active`, `inactive`

---

### 9. trading_signals（交易信号）⭐ 新增

**用途**: 记录量化系统生成的买卖点信号，用于K线图标注和准确率统计

```sql
CREATE TABLE trading_signals (
    signal_id VARCHAR(50) PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    date DATE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    confidence INT NOT NULL,
    reasons TEXT NOT NULL,
    operator VARCHAR(50) DEFAULT 'Agent-v2',
    status VARCHAR(20) DEFAULT 'pending',
    executed BOOLEAN DEFAULT FALSE,
    executed_price DECIMAL(10, 2),
    executed_time DATETIME,
    position_size VARCHAR(20),
    pnl_current DECIMAL(10, 2),
    pnl_percentage DECIMAL(10, 4),
    pnl_realized DECIMAL(10, 2),
    is_error BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(50),
    error_feedback TEXT,
    marked_by VARCHAR(50),
    marked_time DATETIME,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_symbol_date (symbol, date),
    INDEX idx_signal_type (signal_type),
    INDEX idx_operator (operator),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp),
    INDEX idx_executed (executed),
    INDEX idx_is_error (is_error)
);
```

**字段说明**:
- `signal_id`: 信号唯一ID，格式 `signal_NNN`
- `timestamp`: 信号生成时间戳
- `date`: 信号日期（用于K线图定位）
- `symbol`: 股票代码
- `signal_type`: 信号类型 - `buy`, `sell`, `hold`
- `price`: 信号价格
- `confidence`: 置信度 (0-100)
- `reasons`: 信号原因列表（JSON数组）
- `operator`: 操作者 - `Agent-v2`, `User`, `System`
- `status`: 状态 - `pending`, `approved`, `rejected`, `executed`
- `executed`: 是否已执行
- `executed_price`: 实际执行价格
- `executed_time`: 执行时间
- `position_size`: 仓位大小（如 "10%"）
- `pnl_current`: 当前盈亏（未平仓）
- `pnl_percentage`: 盈亏百分比
- `pnl_realized`: 已实现盈亏（已平仓）
- `is_error`: 是否被标记为错误
- `error_type`: 错误类型 - `wrong_timing`, `wrong_price`, `wrong_reason`, `other`
- `error_feedback`: 错误反馈说明
- `marked_by`: 标记人
- `marked_time`: 标记时间
- `metadata`: 额外元数据（JSON格式）

**示例数据**:
```sql
INSERT INTO trading_signals VALUES (
    'signal_001',
    '2026-05-10 10:45:30',
    '2026-05-10',
    '600519',
    'buy',
    1820.00,
    85,
    '["RSI超卖(28)", "MACD金叉", "布林带下轨支撑"]',
    'Agent-v2',
    'executed',
    TRUE,
    1825.00,
    '2026-05-10 10:50:00',
    '10%',
    230.00,
    12.6,
    NULL,
    FALSE,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    '2026-05-10 10:45:30',
    '2026-05-20 14:15:00'
);
```

---

## 索引设计

### 性能优化索引

```sql
-- agent_logs 高频查询索引
CREATE INDEX idx_agent_logs_date_action ON agent_logs(DATE(timestamp), action_type);
CREATE INDEX idx_agent_logs_symbol_date ON agent_logs(symbol, DATE(timestamp));

-- orders 审批流程索引
CREATE INDEX idx_orders_pending ON orders(status, submitted_at) WHERE status = 'pending';
CREATE INDEX idx_orders_account_status ON orders(account_id, status);

-- positions 持仓查询索引
CREATE INDEX idx_positions_active ON positions(account_id, status) WHERE status = 'active';

-- agent_decisions 绩效统计索引
CREATE INDEX idx_decisions_feedback_date ON agent_decisions(feedback, DATE(timestamp));
CREATE INDEX idx_decisions_symbol_date ON agent_decisions(symbol, DATE(timestamp));

-- data_snapshots 快照查询索引
CREATE INDEX idx_snapshots_symbol_type_time ON data_snapshots(symbol, data_type, timestamp DESC);

-- trading_signals 买卖点查询索引 ⭐ 新增
CREATE INDEX idx_signals_symbol_date ON trading_signals(symbol, date DESC);
CREATE INDEX idx_signals_type_status ON trading_signals(signal_type, status);
CREATE INDEX idx_signals_operator_date ON trading_signals(operator, date DESC);
CREATE INDEX idx_signals_executed ON trading_signals(executed, date DESC);
CREATE INDEX idx_signals_error ON trading_signals(is_error, date DESC);
```

---

## 数据关系图

```
accounts (账户)
    ↓ 1:N
positions (持仓) ←→ position_history (持仓历史)
    ↓ 1:N
orders (订单) ←→ agent_logs (操作日志)
    ↓ 1:1
agent_decisions (决策记录)
    ↓ 1:N
data_snapshots (数据快照)

trading_signals (交易信号) ⭐ 新增
    ↓ 关联
orders (订单) - 信号可能触发订单
positions (持仓) - 信号关联持仓盈亏

approval_rules (审批规则) → orders (订单)
```

**表数量**: 9张核心表（原8张 + 1张新增）

---

## 数据字典

### 操作类型 (action_type)
- `scan`: 市场扫描
- `analyze`: 股票分析
- `signal`: 信号生成
- `trade`: 交易执行
- `monitor`: 持仓监控

### 订单状态 (order.status)
- `pending`: 待审批
- `approved`: 已批准
- `rejected`: 已拒绝
- `executed`: 已执行
- `cancelled`: 已取消

### 决策类型 (decision)
- `buy`: 买入
- `sell`: 卖出
- `hold`: 持有

### 反馈类型 (feedback)
- `correct`: 正确
- `wrong`: 错误
- `partial`: 部分正确
- `pending`: 待验证

### 数据类型 (data_type)
- `quote`: 实时行情
- `kline`: K线数据
- `financial`: 财务数据
- `fund_flow`: 资金流向
- `technical`: 技术指标

---

## 数据保留策略

### 日志数据
- `agent_logs`: 保留90天
- `data_snapshots`: 保留30天

### 交易数据
- `orders`: 永久保留
- `positions`: 永久保留
- `position_history`: 永久保留

### 决策数据
- `agent_decisions`: 永久保留（用于训练）

---

## 数据备份策略

### 每日备份
- 所有交易相关表（orders, positions, position_history）
- Agent决策记录（agent_decisions）

### 每周备份
- 完整数据库备份

### 实时备份
- 关键操作触发增量备份（大额交易、重要决策）
