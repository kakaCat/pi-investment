# 因子和信号生成流程设计

## 当前问题

1. **信号数据只存文件，不存数据库**
   - `generate_signals.py` 只写入 `quant/.pi-invest/signals.json`
   - API 只从 JSON 文件读取，无法查询历史信号
   - 删除数据库数据后，API 仍返回文件中的旧数据

2. **缺少信号表**
   - 数据库中没有 `signals` 表
   - 无法追踪信号历史、回测验证、统计分析

3. **因子和信号流程不清晰**
   - 因子计算和信号生成是独立脚本
   - 没有统一的调度和依赖管理
   - 数据一致性无法保证

## 数据库表结构

### 现有表

```sql
-- 股票基础信息
quant.stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    market TEXT,
    industry TEXT,
    ...
)

-- K线数据
quant.daily_klines (
    symbol TEXT,
    trade_date DATE,
    open, high, low, close, volume, amount,
    PRIMARY KEY (symbol, trade_date)
)

-- 因子值
quant.factor_values (
    symbol TEXT,
    factor_date DATE,
    factor_name TEXT,
    factor_value DOUBLE PRECISION,
    PRIMARY KEY (symbol, factor_date, factor_name)
)
```

### 需要新增的表

```sql
-- 交易信号表
CREATE TABLE IF NOT EXISTS quant.trading_signals (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    signal_date DATE NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
    strategy_name TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    price DOUBLE PRECISION NOT NULL,
    reason TEXT,
    metadata JSONB,  -- 存储策略参数等额外信息
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, signal_date, strategy_name)
);

CREATE INDEX idx_signals_symbol_date ON quant.trading_signals(symbol, signal_date DESC);
CREATE INDEX idx_signals_date ON quant.trading_signals(signal_date DESC);
CREATE INDEX idx_signals_strategy ON quant.trading_signals(strategy_name);
CREATE INDEX idx_signals_type ON quant.trading_signals(signal_type);

-- 信号-因子关联表（核心：记录信号使用了哪些因子）
CREATE TABLE IF NOT EXISTS quant.signal_factors (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER NOT NULL REFERENCES quant.trading_signals(id) ON DELETE CASCADE,
    factor_name TEXT NOT NULL,
    factor_value DOUBLE PRECISION NOT NULL,
    factor_weight DOUBLE PRECISION,  -- 因子在信号生成中的权重/贡献度
    trigger_condition TEXT,  -- 触发条件，如 "RSI6 < 30"
    is_primary BOOLEAN DEFAULT FALSE,  -- 是否为主要触发因子
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_signal_factors_signal_id ON quant.signal_factors(signal_id);
CREATE INDEX idx_signal_factors_factor_name ON quant.signal_factors(factor_name);

-- 信号执行记录表（用于回测验证）
CREATE TABLE IF NOT EXISTS quant.signal_executions (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER NOT NULL REFERENCES quant.trading_signals(id) ON DELETE CASCADE,
    execution_date DATE NOT NULL,
    execution_price DOUBLE PRECISION NOT NULL,
    quantity INTEGER NOT NULL,
    commission DOUBLE PRECISION,
    status TEXT NOT NULL CHECK (status IN ('pending', 'executed', 'cancelled', 'expired')),
    pnl DOUBLE PRECISION,  -- 盈亏（平仓后计算）
    close_date DATE,
    close_price DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_executions_signal_id ON quant.signal_executions(signal_id);
CREATE INDEX idx_executions_date ON quant.signal_executions(execution_date DESC);
```

## 信号-因子关联的核心价值

### 1. 可追溯性（Traceability）
- 每个信号都能追溯到具体的因子值
- 可以验证信号生成逻辑是否正确
- 便于调试和问题排查

**示例：**
```sql
-- 查询某个信号使用了哪些因子
SELECT * FROM quant.signal_factors WHERE signal_id = 12345;

-- 验证信号生成逻辑
SELECT 
    s.symbol,
    s.signal_type,
    s.strategy_name,
    sf.factor_name,
    sf.factor_value,
    sf.trigger_condition
FROM quant.trading_signals s
JOIN quant.signal_factors sf ON s.id = sf.signal_id
WHERE s.id = 12345;
```

### 2. 可解释性（Explainability）
- 清楚地知道为什么生成这个信号
- 哪些因子触发了条件
- 各因子的贡献度

**示例：**
```
信号：600519 买入信号
原因：RSI6超卖反转，成交量放大
因子详情：
  - RSI6 = 28.5 (权重60%, 触发条件: RSI6 < 30) ✓ 主要因子
  - RSI12 = 35.2 (权重20%, 触发条件: RSI12 < 40) ✓
  - VolumeRatio = 1.8 (权重20%, 触发条件: VolumeRatio > 1.5) ✓
```

### 3. 可优化性（Optimizability）
- 分析哪些因子对信号质量贡献最大
- 优化因子权重和阈值
- 淘汰低效因子，引入新因子

**示例：**
```sql
-- 分析因子对收益的贡献
SELECT 
    sf.factor_name,
    COUNT(*) as signal_count,
    AVG(se.pnl) as avg_pnl,
    STDDEV(se.pnl) as pnl_stddev,
    COUNT(CASE WHEN se.pnl > 0 THEN 1 END)::FLOAT / COUNT(*) as win_rate
FROM quant.signal_factors sf
JOIN quant.trading_signals s ON sf.signal_id = s.id
JOIN quant.signal_executions se ON s.id = se.signal_id
WHERE se.status = 'executed' AND se.close_date IS NOT NULL
GROUP BY sf.factor_name
ORDER BY avg_pnl DESC;

-- 结果示例：
-- factor_name | signal_count | avg_pnl | pnl_stddev | win_rate
-- RSI6        | 150          | 2.5%    | 1.2%       | 0.65
-- MACD_DIF    | 120          | 2.1%    | 1.5%       | 0.62
-- VolumeRatio | 200          | 0.8%    | 2.0%       | 0.52
```

### 4. 多因子组合策略（Multi-Factor Strategy）
- 支持复杂的多因子组合策略
- 不同因子可以有不同的权重
- 可以设置主要因子和辅助因子

**示例：**
```python
# 多因子组合策略
def generate_multi_factor_signal(symbol, date, factors):
    """综合多个因子生成信号"""
    score = 0
    signal_factors = []
    
    # 趋势因子（权重40%）
    if factors['MA5'] > factors['MA20']:
        score += 0.4
        signal_factors.append({
            'factor_name': 'MA5_MA20_CROSS',
            'factor_value': factors['MA5'] / factors['MA20'],
            'factor_weight': 0.4,
            'trigger_condition': 'MA5 > MA20',
            'is_primary': True
        })
    
    # 动量因子（权重30%）
    if factors['RSI6'] < 30:
        score += 0.3
        signal_factors.append({
            'factor_name': 'RSI6',
            'factor_value': factors['RSI6'],
            'factor_weight': 0.3,
            'trigger_condition': 'RSI6 < 30',
            'is_primary': True
        })
    
    # 成交量因子（权重30%）
    if factors['VolumeRatio'] > 1.5:
        score += 0.3
        signal_factors.append({
            'factor_name': 'VolumeRatio',
            'factor_value': factors['VolumeRatio'],
            'factor_weight': 0.3,
            'trigger_condition': 'VolumeRatio > 1.5',
            'is_primary': False
        })
    
    # 只有综合得分 > 0.6 才生成信号
    if score >= 0.6:
        return {
            'signal_type': 'BUY',
            'confidence': score,
            'factors': signal_factors
        }
    
    return None
```

### 5. 因子有效性验证（Factor Validation）
- 回测验证因子的有效性
- 统计因子在不同市场环境下的表现
- 识别失效的因子

**示例：**
```sql
-- 按市场环境分析因子表现
SELECT 
    sf.factor_name,
    CASE 
        WHEN s.signal_date BETWEEN '2025-01-01' AND '2025-06-30' THEN '牛市'
        WHEN s.signal_date BETWEEN '2025-07-01' AND '2025-12-31' THEN '震荡'
        ELSE '熊市'
    END as market_phase,
    AVG(se.pnl) as avg_pnl,
    COUNT(CASE WHEN se.pnl > 0 THEN 1 END)::FLOAT / COUNT(*) as win_rate
FROM quant.signal_factors sf
JOIN quant.trading_signals s ON sf.signal_id = s.id
JOIN quant.signal_executions se ON s.id = se.signal_id
WHERE se.status = 'executed' AND se.close_date IS NOT NULL
GROUP BY sf.factor_name, market_phase
ORDER BY sf.factor_name, market_phase;
```

## 数据流程设计

### 1. 数据采集层（Data Collection）

```
定时任务（每日收盘后）
├── 下载股票列表 → quant.stocks
├── 下载K线数据 → quant.daily_klines
└── 数据质量检查
```

**脚本：**
- `scripts/download_stock_list.py`
- `scripts/download_klines.py`

### 2. 因子计算层（Factor Calculation）

```
输入：quant.daily_klines
处理：计算42个技术因子
输出：quant.factor_values

因子类型：
├── 趋势类：MA5, MA10, MA20, MA60, EMA12, EMA26
├── 动量类：RSI6, RSI12, RSI24, ROC12, MOM10
├── 波动类：ATR14, BollingerBands, StdDev20
├── 成交量：OBV, VolumeRatio, MFI14
└── 其他：MACD, KDJ, CCI, WilliamsR, EMV
```

**脚本：**
- `scripts/calculate_factors.py` - 单线程计算
- `scripts/calculate_factors_parallel.py` - 并行计算（推荐）

**优化：**
- 增量计算：只计算新增日期的因子
- 并行计算：按股票分组并行
- 缓存机制：避免重复计算

### 3. 信号生成层（Signal Generation）

```
输入：quant.factor_values + quant.daily_klines
处理：运行5种策略
输出：quant.trading_signals + quant.signal_factors + signals.json（兼容）

策略及其依赖因子：
├── RSI反转策略
│   ├── 主要因子：RSI6, RSI12
│   ├── 辅助因子：Volume, VolumeRatio
│   └── 触发条件：RSI6 < 30 (超卖买入) 或 RSI6 > 70 (超买卖出)
│
├── 均线突破策略
│   ├── 主要因子：MA5, MA20
│   ├── 辅助因子：Volume, ATR14
│   └── 触发条件：MA5上穿MA20 (金叉买入) 或 MA5下穿MA20 (死叉卖出)
│
├── MACD策略
│   ├── 主要因子：MACD_DIF, MACD_DEA, MACD_HIST
│   ├── 辅助因子：Volume
│   └── 触发条件：DIF上穿DEA (金叉买入) 或 DIF下穿DEA (死叉卖出)
│
├── 布林带策略
│   ├── 主要因子：BB_UPPER, BB_MIDDLE, BB_LOWER, Close
│   ├── 辅助因子：ATR14, Volume
│   └── 触发条件：价格突破下轨 (买入) 或 突破上轨 (卖出)
│
└── KDJ策略
    ├── 主要因子：KDJ_K, KDJ_D, KDJ_J
    ├── 辅助因子：Volume
    └── 触发条件：J < 20 (超卖买入) 或 J > 80 (超买卖出)
```

**脚本：**
- `scripts/generate_signals.py`

**修改点：**
1. 添加数据库写入逻辑（同时写入 trading_signals 和 signal_factors）
2. 记录每个信号使用的因子及其值
3. 记录因子的触发条件和权重
4. 保留 JSON 文件输出（向后兼容）
5. 支持增量生成（只生成指定日期）
6. 添加信号去重逻辑

**信号生成示例：**
```python
# 生成一个RSI反转买入信号
signal = {
    'symbol': '600519',
    'signal_date': '2026-05-19',
    'signal_type': 'BUY',
    'strategy_name': 'RSI_REVERSAL',
    'confidence': 0.85,
    'price': 1850.00,
    'reason': 'RSI6超卖反转，成交量放大'
}

# 关联的因子
signal_factors = [
    {
        'factor_name': 'RSI6',
        'factor_value': 28.5,
        'factor_weight': 0.6,
        'trigger_condition': 'RSI6 < 30',
        'is_primary': True
    },
    {
        'factor_name': 'RSI12',
        'factor_value': 35.2,
        'factor_weight': 0.2,
        'trigger_condition': 'RSI12 < 40',
        'is_primary': False
    },
    {
        'factor_name': 'VolumeRatio',
        'factor_value': 1.8,
        'factor_weight': 0.2,
        'trigger_condition': 'VolumeRatio > 1.5',
        'is_primary': False
    }
]
```

### 4. API查询层（API Layer）

```
GET /api/signals
├── 从数据库查询：quant.trading_signals
├── JOIN quant.signal_factors 获取关联因子
├── 支持过滤：日期、股票、策略、信号类型、置信度
├── 支持分页：limit, offset
└── 返回格式：{count, signals: [{...signal, factors: [...]}]}

GET /api/signals/history
├── 查询历史信号
├── 支持时间范围查询
├── 支持聚合统计
└── 包含因子信息

GET /api/signals/:id
├── 查询单个信号详情
├── 包含完整的因子列表
└── 包含执行记录

GET /api/signals/:id/factors
├── 查询信号使用的所有因子
├── 按权重排序
└── 显示触发条件

POST /api/signals/backtest
├── 回测信号效果
├── 分析因子贡献度
└── 返回收益率、胜率等指标

GET /api/factors/importance
├── 分析因子重要性
├── 统计因子在成功信号中的出现频率
└── 计算因子对收益的贡献度
```

**API 响应示例：**
```json
{
  "count": 1,
  "signals": [
    {
      "id": 12345,
      "symbol": "600519",
      "signal_date": "2026-05-19",
      "signal_type": "BUY",
      "strategy_name": "RSI_REVERSAL",
      "confidence": 0.85,
      "price": 1850.00,
      "reason": "RSI6超卖反转，成交量放大",
      "factors": [
        {
          "factor_name": "RSI6",
          "factor_value": 28.5,
          "factor_weight": 0.6,
          "trigger_condition": "RSI6 < 30",
          "is_primary": true
        },
        {
          "factor_name": "RSI12",
          "factor_value": 35.2,
          "factor_weight": 0.2,
          "trigger_condition": "RSI12 < 40",
          "is_primary": false
        },
        {
          "factor_name": "VolumeRatio",
          "factor_value": 1.8,
          "factor_weight": 0.2,
          "trigger_condition": "VolumeRatio > 1.5",
          "is_primary": false
        }
      ],
      "created_at": "2026-05-19T16:30:00Z"
    }
  ]
}
```

## 实现计划

### Phase 1: 数据库表创建（优先级：高）

- [ ] 创建 `quant.trading_signals` 表
- [ ] 创建 `quant.signal_executions` 表
- [ ] 添加索引和约束
- [ ] 编写迁移脚本

### Phase 2: 信号生成脚本改造（优先级：高）

- [ ] 修改 `generate_signals.py`
  - [ ] 添加数据库写入函数 `save_signals_to_db()`
  - [ ] 添加因子关联写入函数 `save_signal_factors()`
  - [ ] 每个策略记录使用的因子及其值
  - [ ] 计算因子权重和触发条件
  - [ ] 保留 JSON 文件输出（向后兼容）
  - [ ] 添加信号去重逻辑（同一天同一股票同一策略只保留最高置信度）
  - [ ] 支持增量生成（`--date` 参数）
  - [ ] 添加事务处理（全部成功或全部回滚）

**策略改造示例（RSI反转策略）：**
```python
def generate_rsi_reversal_signal(symbol, date, factors):
    """生成RSI反转信号，并记录使用的因子"""
    rsi6 = factors.get('RSI6')
    rsi12 = factors.get('RSI12')
    volume_ratio = factors.get('VolumeRatio')
    
    signal = None
    signal_factors = []
    
    # 超卖买入
    if rsi6 < 30:
        signal = {
            'symbol': symbol,
            'signal_date': date,
            'signal_type': 'BUY',
            'strategy_name': 'RSI_REVERSAL',
            'confidence': calculate_confidence(rsi6, rsi12, volume_ratio),
            'price': factors.get('Close'),
            'reason': f'RSI6超卖反转({rsi6:.1f})'
        }
        
        # 记录主要因子
        signal_factors.append({
            'factor_name': 'RSI6',
            'factor_value': rsi6,
            'factor_weight': 0.6,
            'trigger_condition': 'RSI6 < 30',
            'is_primary': True
        })
        
        # 记录辅助因子
        if rsi12 < 40:
            signal_factors.append({
                'factor_name': 'RSI12',
                'factor_value': rsi12,
                'factor_weight': 0.2,
                'trigger_condition': 'RSI12 < 40',
                'is_primary': False
            })
        
        if volume_ratio > 1.5:
            signal_factors.append({
                'factor_name': 'VolumeRatio',
                'factor_value': volume_ratio,
                'factor_weight': 0.2,
                'trigger_condition': 'VolumeRatio > 1.5',
                'is_primary': False
            })
    
    return signal, signal_factors
```

### Phase 3: API 端点改造（优先级：高）

- [ ] 修改 `/api/signals` 从数据库读取
  - [ ] JOIN `signal_factors` 表获取因子信息
  - [ ] 支持日期过滤
  - [ ] 支持股票过滤
  - [ ] 支持策略过滤
  - [ ] 支持信号类型过滤
  - [ ] 支持置信度过滤
  - [ ] 支持分页
  - [ ] 返回格式包含 factors 数组
- [ ] 添加 `/api/signals/history` 端点
- [ ] 添加 `/api/signals/:id` 端点（包含完整因子列表）
- [ ] 添加 `/api/signals/:id/factors` 端点（查询信号的所有因子）
- [ ] 添加 `/api/factors/importance` 端点（分析因子重要性）
- [ ] 保留 JSON 文件读取作为降级方案

**SQL 查询示例：**
```sql
-- 查询信号及其关联因子
SELECT 
    s.id,
    s.symbol,
    s.signal_date,
    s.signal_type,
    s.strategy_name,
    s.confidence,
    s.price,
    s.reason,
    json_agg(
        json_build_object(
            'factor_name', sf.factor_name,
            'factor_value', sf.factor_value,
            'factor_weight', sf.factor_weight,
            'trigger_condition', sf.trigger_condition,
            'is_primary', sf.is_primary
        ) ORDER BY sf.factor_weight DESC
    ) as factors
FROM quant.trading_signals s
LEFT JOIN quant.signal_factors sf ON s.id = sf.signal_id
WHERE s.signal_date = '2026-05-19'
GROUP BY s.id
ORDER BY s.confidence DESC;

-- 分析因子重要性（统计因子在成功信号中的出现频率）
SELECT 
    sf.factor_name,
    COUNT(*) as usage_count,
    AVG(sf.factor_weight) as avg_weight,
    AVG(se.pnl) as avg_pnl,
    COUNT(CASE WHEN se.pnl > 0 THEN 1 END)::FLOAT / COUNT(*) as win_rate
FROM quant.signal_factors sf
JOIN quant.trading_signals s ON sf.signal_id = s.id
LEFT JOIN quant.signal_executions se ON s.id = se.signal_id
WHERE se.status = 'executed' AND se.close_date IS NOT NULL
GROUP BY sf.factor_name
ORDER BY avg_pnl DESC;
```

### Phase 4: 因子计算优化（优先级：中）

- [ ] 实现增量计算逻辑
  - [ ] 检查最新因子日期
  - [ ] 只计算新增日期
  - [ ] 避免重复计算
- [ ] 优化并行计算性能
- [ ] 添加因子质量检查

### Phase 5: 调度和监控（优先级：中）

- [ ] 统一调度脚本 `scripts/daily_pipeline.py`
  ```python
  1. 下载K线数据
  2. 计算因子（增量）
  3. 生成信号
  4. 发送通知
  ```
- [ ] 添加任务状态监控
- [ ] 添加数据质量监控
- [ ] 添加告警机制

### Phase 6: 回测和验证（优先级：低）

- [ ] 实现信号回测功能
- [ ] 统计信号胜率、收益率
- [ ] 优化策略参数
- [ ] 生成回测报告

## 数据一致性保证

### 1. 事务处理
- 信号生成使用数据库事务
- 全部成功或全部回滚
- 避免部分写入

### 2. 去重策略
- 同一天同一股票同一策略只保留最高置信度信号
- 使用 `UNIQUE (symbol, signal_date, strategy_name)` 约束
- 使用 `ON CONFLICT DO UPDATE` 更新

### 3. 数据校验
- 检查因子数据完整性
- 检查K线数据完整性
- 检查信号合理性（价格、置信度范围）

### 4. 降级方案
- API 优先读数据库
- 数据库失败时降级到 JSON 文件
- 记录降级事件

## 性能优化

### 1. 因子计算
- 并行计算：按股票分组
- 增量计算：只计算新增日期
- 批量写入：减少数据库IO

### 2. 信号生成
- 批量查询因子数据
- 批量写入信号数据
- 使用连接池

### 3. API 查询
- 添加索引：symbol, signal_date, strategy_name
- 使用分页：避免大结果集
- 添加缓存：热点数据缓存

## 监控指标

### 1. 数据质量
- 因子覆盖率：有因子数据的股票比例
- 信号数量：每日生成的信号数量
- 数据延迟：数据更新时间差

### 2. 性能指标
- 因子计算耗时
- 信号生成耗时
- API 响应时间

### 3. 业务指标
- 信号胜率
- 平均收益率
- 最大回撤

## 向后兼容

1. **保留 JSON 文件**
   - 继续生成 `signals.json`
   - 旧代码可以继续使用

2. **API 响应格式不变**
   - 保持现有响应结构
   - 只改变数据来源

3. **渐进式迁移**
   - 先实现数据库写入
   - 再切换 API 读取
   - 最后移除 JSON 依赖

## 时间估算

- Phase 1: 2小时（表创建和迁移）
- Phase 2: 4小时（信号生成改造）
- Phase 3: 4小时（API 改造）
- Phase 4: 3小时（因子优化）
- Phase 5: 4小时（调度监控）
- Phase 6: 6小时（回测验证）

**总计：23小时**

## 下一步行动

1. 用户确认设计方案
2. 创建数据库表
3. 改造信号生成脚本
4. 改造 API 端点
5. 测试验证
