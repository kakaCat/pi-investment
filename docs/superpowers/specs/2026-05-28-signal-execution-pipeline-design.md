# 信号到执行链路完整设计

**日期**: 2026-05-28  
**作者**: Claude (Opus 4.7)  
**状态**: Draft

## 执行摘要

本设计解决了系统中信号生成与订单执行之间的断层问题。当前系统已生成17,253个交易信号，但0个被执行，36个策略全部处于stopped状态。本方案建立完整的"信号生成 → 风控检查 → 订单创建 → 执行确认"自动化链路。

**核心目标**: 将策略信号自动转化为实际交易订单，实现量化投资的闭环。

## 需求确认

### 执行模式
- **选择**: 全自动执行模式
- **说明**: 信号生成后自动通过风控检查并创建订单，无需人工审批
- **适用场景**: 模拟盘、回测、成熟的量化策略

### 触发机制
- **选择**: 定时触发
- **时间**: 每天15:30（A股收盘后）
- **频率**: 仅工作日（周一至周五）
- **原因**: 
  - 收盘后K线数据完整，可准确计算技术指标
  - 符合A股T+1交易制度
  - 生成的信号用于次日开盘交易

### 风控级别
- **选择**: 标准风控
- **检查项**:
  1. 资金充足性检查（买入时现金是否足够）
  2. 持仓充足性检查（卖出时股票是否足够）
  3. 单笔订单金额上限（不超过总资产20%）
  4. 仓位集中度检查（单只股票不超过30%）
  5. 行业集中度检查（单个行业不超过40%）
  6. 日内交易次数限制（单只股票最多5次）
  7. 止损价格合理性验证（3%-15%范围）

### 失败处理
- **选择**: 记录并跳过
- **行为**: 
  - 风控不通过的信号标记为`rejected`，记录拒绝原因
  - 系统错误的信号标记为`error`，记录错误信息
  - 继续处理下一个信号，不阻塞整体流程
  - 每日生成失败报告供人工审查

### 订单执行方式
- **选择**: 限价单
- **定价策略**: 
  - 买入：收盘价 × 1.01（加1%）
  - 卖出：收盘价 × 0.99（减1%）
- **优势**: 价格可控，避免滑点过大
- **劣势**: 可能因价格不合适而无法成交（可接受）

## 架构设计

### 整体流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     每天 15:30 定时触发                          │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              SignalExecutionScheduler (调度器)                   │
│  职责：编排整个信号到执行的完整流程                               │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                  ↓
┌──────────────┐                  ┌──────────────┐
│ 1. 策略运行   │                  │ 2. 信号收集   │
│ 运行所有启用  │ ────────────────→│ 收集新生成的  │
│ 的策略        │                  │ 信号          │
└──────────────┘                  └──────┬───────┘
                                         ↓
                                  ┌──────────────┐
                                  │ 3. 批量风控   │
                                  │ 资金/仓位/    │
                                  │ 集中度检查    │
                                  └──────┬───────┘
                                         ↓
                                  ┌──────────────┐
                                  │ 4. 订单创建   │
                                  │ 通过风控的    │
                                  │ 信号创建订单  │
                                  └──────┬───────┘
                                         ↓
                                  ┌──────────────┐
                                  │ 5. 执行日志   │
                                  │ 记录成功/失败 │
                                  │ 统计          │
                                  └──────────────┘
```

### 核心组件

**新增组件**:
1. **SignalExecutionScheduler** - 信号执行调度器（核心）
   - 位置: `quantsys-v2/services/signal_execution_scheduler.py`
   - 职责: 编排整个执行流程

2. **RiskCheckService** - 风控检查服务
   - 位置: `quantsys-v2/services/risk_check_service.py`
   - 职责: 执行标准风控检查

3. **SignalExecutionLogRepository** - 执行日志Repository
   - 位置: `quantsys-v2/repositories/signal_execution_log_repository.py`
   - 职责: 管理执行日志数据

4. **RiskConfigRepository** - 风控配置Repository
   - 位置: `quantsys-v2/repositories/risk_config_repository.py`
   - 职责: 管理风控配置数据

**复用组件**:
1. **StrategyCodeService** - 策略运行（已有）
2. **OrderService** - 订单创建（已有）
3. **SignalRepository** - 信号存储（已有）
4. **Cron Scheduler** - 定时任务（已有）

### 方案选择

本设计采用**方案A：集中式调度器**架构。

**对比的其他方案**:
- 方案B：事件驱动架构（解耦性强但调试复杂）
- 方案C：Pipeline模式（最简单但扩展性差）

**选择理由**:
1. 全自动执行需要强事务性和可靠性，集中式调度器最合适
2. 易于监控：所有执行逻辑在一个地方，出问题容易定位
3. 性能好：批量处理17,253个信号比逐个处理快得多
4. 实现成本适中：不需要学习新模式，直接写业务逻辑即可

## 数据模型设计

### 信号状态流转

扩展现有`quant.signals`表的状态管理：

```sql
-- status 字段的可能值
'pending'    -- 新生成，等待处理
'approved'   -- 通过风控检查（新增自动审批状态）
'rejected'   -- 风控不通过
'executed'   -- 已创建订单
'error'      -- 处理出错
'expired'    -- 已过期（超过有效期未执行）
```

**新增字段**:
```sql
ALTER TABLE quant.signals ADD COLUMN reject_reason TEXT;
```

### 执行日志表（新增）

```sql
CREATE TABLE IF NOT EXISTS quant.signal_execution_logs (
    id SERIAL PRIMARY KEY,
    execution_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms INTEGER,
    
    -- 统计数据
    strategies_run INTEGER DEFAULT 0,
    signals_generated INTEGER DEFAULT 0,
    signals_approved INTEGER DEFAULT 0,
    signals_rejected INTEGER DEFAULT 0,
    orders_created INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    
    -- 详细结果
    execution_details JSONB,
    
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signal_execution_logs_date ON quant.signal_execution_logs(execution_date);
CREATE INDEX idx_signal_execution_logs_status ON quant.signal_execution_logs(status);
```

**execution_details JSONB结构**:
```json
{
  "strategies": [
    {"id": 1, "name": "双均线", "signals": 5, "duration_ms": 120}
  ],
  "risk_check_summary": {
    "total_checked": 100,
    "passed": 80,
    "rejected_reasons": {
      "insufficient_funds": 10,
      "position_limit": 5,
      "concentration_limit": 5
    }
  },
  "orders_summary": {
    "buy_orders": 50,
    "sell_orders": 30,
    "total_amount": 5000000
  }
}
```

### 风控配置表（新增）

```sql
CREATE TABLE IF NOT EXISTS quant.risk_config (
    id SERIAL PRIMARY KEY,
    config_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    
    -- 资金风控
    max_single_order_percent DECIMAL(5,2) DEFAULT 20.00,
    max_daily_trade_amount DECIMAL(15,2),
    min_cash_reserve_percent DECIMAL(5,2) DEFAULT 10.00,
    
    -- 仓位风控
    max_position_percent DECIMAL(5,2) DEFAULT 30.00,
    max_sector_percent DECIMAL(5,2) DEFAULT 40.00,
    max_total_position_percent DECIMAL(5,2) DEFAULT 95.00,
    
    -- 交易频率风控
    max_daily_trades INTEGER DEFAULT 50,
    max_single_stock_trades INTEGER DEFAULT 5,
    
    -- 止损风控
    require_stop_loss BOOLEAN DEFAULT true,
    min_stop_loss_percent DECIMAL(5,2) DEFAULT 3.00,
    max_stop_loss_percent DECIMAL(5,2) DEFAULT 15.00,
    
    config_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO quant.risk_config (config_name) VALUES ('default')
ON CONFLICT (config_name) DO NOTHING;
```

## 详细设计将在后续部分继续...


## 核心服务实现

### SignalExecutionScheduler（调度器）

**文件**: `quantsys-v2/services/signal_execution_scheduler.py`

**职责**:
- 编排信号到订单的完整执行流程
- 运行启用的策略
- 收集生成的信号
- 批量风控检查
- 创建订单
- 记录执行日志

**核心方法**:

```python
class SignalExecutionScheduler:
    def execute_daily_signals(self) -> Dict[str, Any]:
        """
        执行每日信号处理流程（15:30定时调用）
        
        Returns:
            执行结果摘要
        """
        # 1. 运行策略并生成信号
        strategy_results = self._run_strategies()
        
        # 2. 收集今日生成的信号
        signals = self._collect_signals(execution_date)
        
        # 3. 批量风控检查
        approved_signals, rejected_signals = self._batch_risk_check(signals)
        
        # 4. 批量创建订单
        orders_created = self._batch_create_orders(approved_signals)
        
        # 5. 更新信号状态
        self._update_signal_status(approved_signals, rejected_signals)
        
        # 6. 记录执行结果
        return execution_summary
```

**关键实现细节**:

1. **策略运行** (`_run_strategies`):
   - 查询所有`is_active=true`的策略
   - 逐个调用`StrategyCodeService.run_strategy()`
   - 记录每个策略的执行时间和生成信号数
   - 捕获异常，不因单个策略失败而中断整体流程

2. **信号收集** (`_collect_signals`):
   - 查询今日生成的`status='pending'`信号
   - 只处理待处理状态的信号，避免重复处理

3. **批量风控检查** (`_batch_risk_check`):
   - 遍历所有信号，调用`RiskCheckService.check_signal()`
   - 将信号分为通过和拒绝两组
   - 记录每个拒绝信号的原因

4. **批量创建订单** (`_batch_create_orders`):
   - 对通过风控的信号创建订单
   - 获取最新K线数据计算限价
   - 买入：收盘价 × 1.01
   - 卖出：收盘价 × 0.99
   - 调用`order_service.create_order()`

5. **状态更新** (`_update_signal_status`):
   - 通过的信号 → `status='executed'`
   - 拒绝的信号 → `status='rejected'`, 记录`reject_reason`

**性能优化**:
- 批量查询K线数据，避免N+1查询
- 批量更新信号状态
- 预加载账户和持仓信息

### RiskCheckService（风控检查）

**文件**: `quantsys-v2/services/risk_check_service.py`

**职责**:
- 执行标准风控检查
- 计算建议交易数量
- 返回检查结果和拒绝原因

**核心方法**:

```python
class RiskCheckService:
    def check_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查信号是否通过风控
        
        Returns:
            {
                'passed': True/False,
                'reason': '拒绝原因',
                'checks': {...},
                'quantity': 100,
                'warnings': []
            }
        """
```

**检查项详细说明**:

1. **资金充足性检查** (`_check_funds`):
   - 计算所需资金 = 股票金额 + 佣金（0.03%）
   - 检查可用资金 = 现金 - 最低储备（10%）
   - 拒绝条件：所需资金 > 可用资金

2. **持仓充足性检查** (`_check_holding`):
   - 查询当前持仓数量
   - 拒绝条件：持仓数量 < 卖出数量

3. **单笔订单限制** (`_check_single_order_limit`):
   - 计算订单金额占总资产比例
   - 拒绝条件：订单金额 > 总资产 × 20%

4. **仓位集中度检查** (`_check_position_concentration`):
   - 计算买入后该股票占总资产比例
   - 拒绝条件：仓位比例 > 30%
   - 警告：仓位比例 > 24%（80%阈值）

5. **行业集中度检查** (`_check_sector_concentration`):
   - 查询股票所属行业
   - 计算该行业总仓位占比
   - 拒绝条件：行业仓位 > 40%

6. **日内交易次数限制** (`_check_daily_trade_limit`):
   - 查询今日该股票交易次数
   - 拒绝条件：交易次数 >= 5次

7. **止损价格合理性** (`_check_stop_loss`):
   - 解析信号中的止损设置
   - 计算止损幅度
   - 拒绝条件：止损幅度 < 3% 或 > 15%

**数量计算逻辑**:

买入数量计算：
```python
def _calculate_buy_quantity(self, signal, current_price, account):
    # 优先使用信号中的数量
    if signal.get('quantity'):
        return (signal['quantity'] // 100) * 100
    
    # 否则根据仓位配置计算
    position_percent = signal.get('risk_management', {})
                             .get('position_sizing', {})
                             .get('percent', 10.0)
    
    target_amount = account['total_assets'] * (position_percent / 100)
    quantity = int(target_amount / current_price)
    
    # 向下取整到100的整数倍，至少100股
    return max(100, (quantity // 100) * 100)
```

卖出数量计算：
```python
def _calculate_sell_quantity(self, signal):
    # 使用信号数量或全部卖出
    if signal.get('quantity'):
        return signal['quantity']
    
    holding = self.ds.portfolio.get_holding(signal['symbol'])
    return holding['quantity'] if holding else 0
```


## API接口设计

### 手动触发执行

```
POST /api/signal-execution/trigger
Content-Type: application/json

{
  "execution_date": "2026-05-28"  // 可选，默认今天
}

Response:
{
  "success": true,
  "data": {
    "execution_date": "2026-05-28",
    "duration_ms": 1250,
    "strategies_run": 36,
    "signals_generated": 150,
    "signals_approved": 120,
    "signals_rejected": 30,
    "orders_created": 120,
    "errors_count": 0,
    "strategy_details": [...],
    "risk_check_summary": {...},
    "orders_summary": {...}
  }
}
```

### 查询执行日志

```
GET /api/signal-execution/logs?start_date=2026-05-01&end_date=2026-05-28&page=1&page_size=20

Response:
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 123,
        "execution_date": "2026-05-28",
        "start_time": "2026-05-28T15:30:00",
        "end_time": "2026-05-28T15:31:15",
        "duration_ms": 75000,
        "strategies_run": 36,
        "signals_generated": 150,
        "signals_approved": 120,
        "orders_created": 120,
        "status": "completed"
      }
    ],
    "total": 20,
    "page": 1,
    "page_size": 20
  }
}
```

### 查询执行统计

```
GET /api/signal-execution/statistics?days=30

Response:
{
  "success": true,
  "data": {
    "period": {
      "start_date": "2026-04-28",
      "end_date": "2026-05-28",
      "days": 30
    },
    "executions": {
      "total": 22,
      "successful": 21,
      "failed": 1,
      "success_rate": 95.45
    },
    "signals": {
      "total_generated": 3300,
      "total_approved": 2640,
      "total_rejected": 660,
      "approval_rate": 80.00
    },
    "orders": {
      "total_created": 2640,
      "execution_rate": 100.00
    },
    "performance": {
      "avg_duration_ms": 1200,
      "avg_signals_per_day": 150,
      "avg_orders_per_day": 120
    }
  }
}
```

### 查询/更新风控配置

```
GET /api/signal-execution/config

Response:
{
  "success": true,
  "data": {
    "config_name": "default",
    "max_single_order_percent": 20.00,
    "max_position_percent": 30.00,
    "max_sector_percent": 40.00,
    "max_daily_trades": 50,
    "require_stop_loss": true,
    "min_stop_loss_percent": 3.00,
    "max_stop_loss_percent": 15.00,
    ...
  }
}

POST /api/signal-execution/config
Content-Type: application/json

{
  "max_single_order_percent": 25.00,
  "max_position_percent": 35.00
}

Response:
{
  "success": true,
  "data": { /* 更新后的配置 */ },
  "message": "配置更新成功"
}
```

## TypeScript Agent集成

### 新增工具：signal_execution

**文件**: `src/infrastructure/tools/execution/signal-execution-tool.ts`

**功能**:
- 手动触发信号执行
- 查询执行状态和日志
- 查询执行统计
- 管理风控配置

**使用示例**:

```typescript
// 手动触发执行
signal_execution({ action: "trigger" })

// 查询最近执行状态
signal_execution({ action: "status" })

// 查询最近7天日志
signal_execution({ action: "logs", days: 7 })

// 查询最近30天统计
signal_execution({ action: "statistics", days: 30 })

// 查询风控配置
signal_execution({ action: "config" })

// 更新风控配置
signal_execution({ 
  action: "config", 
  config_updates: {
    max_single_order_percent: 25.0
  }
})
```

**输出格式**:

```markdown
## ✅ 信号执行完成

**执行日期**: 2026-05-28
**执行耗时**: 1250ms

### 📊 执行统计

| 项目 | 数量 |
|------|------|
| 运行策略 | 36 |
| 生成信号 | 150 |
| 通过风控 | 120 |
| 风控拒绝 | 30 |
| 创建订单 | 120 |
| 错误数量 | 0 |

### ⚠️ 风控拒绝原因

- 资金不足: 15次
- 仓位超限: 10次
- 行业集中度超限: 5次

### 📋 订单摘要

- 买入订单: 80个
- 卖出订单: 40个
- 总金额: ¥500.00万
```

## 定时任务配置

### Cron配置

**文件**: `quantsys-v2/config/scheduler_config.py`

```python
SCHEDULED_JOBS = [
    {
        'id': 'daily_signal_execution',
        'name': '每日信号执行',
        'func': 'runtime.scheduler.signal_execution_job:execute_daily_signals_job',
        'trigger': 'cron',
        'hour': 15,
        'minute': 30,
        'day_of_week': 'mon-fri',
        'timezone': 'Asia/Shanghai',
        'enabled': True,
        'description': '每天15:30自动运行策略、生成信号、风控检查、创建订单'
    }
]
```

### Job实现

**文件**: `quantsys-v2/runtime/scheduler/signal_execution_job.py`

```python
def execute_daily_signals_job():
    """定时任务入口函数"""
    logger.info("=" * 60)
    logger.info(f"定时任务触发: 每日信号执行 - {datetime.now()}")
    logger.info("=" * 60)
    
    try:
        ds = DataService()
        scheduler = SignalExecutionScheduler(ds)
        result = scheduler.execute_daily_signals()
        
        logger.info("定时任务执行成功")
        logger.info(f"执行摘要: {result}")
        return result
        
    except Exception as e:
        logger.error(f"定时任务执行失败: {str(e)}", exc_info=True)
        raise
```

## 部署方案

### 数据库迁移

**步骤1**: 执行迁移脚本

```bash
cd quantsys-v2
psql -U your_user -d quant_investment -f migrations/add_signal_execution_tables.sql
```

**步骤2**: 验证表创建

```sql
-- 验证表存在
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'quant' 
AND table_name IN ('signal_execution_logs', 'risk_config');

-- 验证默认配置
SELECT * FROM quant.risk_config WHERE config_name = 'default';

-- 验证signals表字段
SELECT column_name FROM information_schema.columns 
WHERE table_schema = 'quant' 
AND table_name = 'signals' 
AND column_name = 'reject_reason';
```

### 代码部署

**新增文件清单**:

```
quantsys-v2/
├── services/
│   ├── signal_execution_scheduler.py      # 调度器核心
│   └── risk_check_service.py              # 风控服务
├── repositories/
│   ├── signal_execution_log_repository.py # 执行日志Repository
│   └── risk_config_repository.py          # 风控配置Repository
├── runtime/scheduler/
│   └── signal_execution_job.py            # 定时任务
├── api/routes/
│   └── signal_execution.py                # API路由
└── migrations/
    └── add_signal_execution_tables.sql    # 数据库迁移

src/infrastructure/tools/execution/
└── signal-execution-tool.ts               # Agent工具
```

**修改文件清单**:

```
quantsys-v2/api/server.py                  # 注册signal_execution_bp
quantsys-v2/config/scheduler_config.py     # 添加定时任务配置
src/infrastructure/tools/index.ts          # 注册signal_execution工具
```

### 配置验证

**步骤1**: 验证quantsys-v2服务运行

```bash
cd quantsys-v2
python start_all.py

# 验证服务健康
curl http://127.0.0.1:5001/api/health
```

**步骤2**: 验证API端点

```bash
# 查询风控配置
curl http://127.0.0.1:5001/api/signal-execution/config

# 查询执行日志
curl http://127.0.0.1:5001/api/signal-execution/logs?page=1&page_size=10
```

**步骤3**: 手动触发测试

```bash
curl -X POST http://127.0.0.1:5001/api/signal-execution/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 监控配置

**日志路径**:
- 调度器日志: `quantsys-v2/logs/signal_execution.log`
- API日志: `quantsys-v2/logs/api.log`
- 定时任务日志: `quantsys-v2/logs/scheduler.log`

**关键监控指标**:
1. 执行成功率（目标 > 95%）
2. 信号通过率（目标 > 70%）
3. 订单创建率（目标 = 100%）
4. 平均执行耗时（目标 < 2000ms）
5. 错误数量（目标 = 0）

**告警规则**:
- 执行失败 → 立即告警
- 信号通过率 < 50% → 警告
- 执行耗时 > 5000ms → 警告
- 连续3天无执行记录 → 告警


## 部署检查清单

### 前置准备

- [ ] 备份现有数据库
  ```bash
  pg_dump -U your_user quant_investment > backup_$(date +%Y%m%d).sql
  ```
- [ ] 确认quantsys-v2服务版本
- [ ] 确认Python环境（Python 3.13）
- [ ] 确认Node.js环境（>= 22.0.0）
- [ ] 准备回滚方案

### 数据库部署

- [ ] 执行迁移脚本 `add_signal_execution_tables.sql`
- [ ] 验证表创建成功
  - [ ] `quant.signal_execution_logs`
  - [ ] `quant.risk_config`
- [ ] 验证默认风控配置已插入
- [ ] 验证`quant.signals`表新增`reject_reason`字段
- [ ] 验证索引创建成功

### 代码部署

**Python服务**:
- [ ] 部署`services/signal_execution_scheduler.py`
- [ ] 部署`services/risk_check_service.py`
- [ ] 部署`repositories/signal_execution_log_repository.py`
- [ ] 部署`repositories/risk_config_repository.py`
- [ ] 部署`runtime/scheduler/signal_execution_job.py`
- [ ] 部署`api/routes/signal_execution.py`
- [ ] 更新`api/server.py`注册Blueprint

**TypeScript Agent**:
- [ ] 部署`src/infrastructure/tools/execution/signal-execution-tool.ts`
- [ ] 更新`src/infrastructure/tools/index.ts`注册工具
- [ ] 重新编译TypeScript代码 `npm run build`

**配置文件**:
- [ ] 更新`quantsys-v2/config/scheduler_config.py`
- [ ] 验证定时任务配置正确

### 功能测试

**基础功能**:
- [ ] 手动触发执行: `POST /api/signal-execution/trigger`
- [ ] 验证策略运行正常（检查日志）
- [ ] 验证信号生成正常（检查signals表）
- [ ] 验证风控检查正常（检查rejected信号）
- [ ] 验证订单创建正常（检查orders表）
- [ ] 验证执行日志记录（检查signal_execution_logs表）

**查询功能**:
- [ ] 查询执行日志: `GET /api/signal-execution/logs`
- [ ] 查询执行统计: `GET /api/signal-execution/statistics`
- [ ] 查询风控配置: `GET /api/signal-execution/config`
- [ ] 更新风控配置: `POST /api/signal-execution/config`

**Agent工具**:
- [ ] 测试`signal_execution({ action: "trigger" })`
- [ ] 测试`signal_execution({ action: "status" })`
- [ ] 测试`signal_execution({ action: "logs", days: 7 })`
- [ ] 测试`signal_execution({ action: "statistics", days: 30 })`
- [ ] 测试`signal_execution({ action: "config" })`

**定时任务**:
- [ ] 验证定时任务已注册（检查scheduler配置）
- [ ] 等待15:30观察自动执行（或手动触发调度器测试）
- [ ] 验证定时任务日志输出正常

### 性能测试

- [ ] 测试100个信号的处理时间（目标 < 1000ms）
- [ ] 测试1000个信号的处理时间（目标 < 5000ms）
- [ ] 测试并发执行（不应出现死锁）
- [ ] 监控数据库连接数
- [ ] 监控内存使用

### 监控配置

- [ ] 配置日志输出路径
- [ ] 配置日志轮转策略
- [ ] 配置告警通知渠道（Feishu/邮件）
- [ ] 设置监控检查任务
- [ ] 验证告警触发正常

### 上线准备

- [ ] 通知相关人员上线时间
- [ ] 准备应急联系方式
- [ ] 准备回滚脚本
- [ ] 文档更新（CLAUDE.md, README）

### 上线后验证

**第一天**:
- [ ] 观察15:30定时执行
- [ ] 检查执行日志状态
- [ ] 检查订单创建数量
- [ ] 检查风控拒绝原因分布
- [ ] 监控系统性能指标

**第一周**:
- [ ] 统计执行成功率
- [ ] 统计信号通过率
- [ ] 统计订单成交率
- [ ] 收集用户反馈
- [ ] 优化风控参数

## 风险评估与缓解

### 风险1: 策略运行失败导致无信号生成

**影响**: 当日无法生成交易信号，错失交易机会

**概率**: 低

**缓解措施**:
- 策略运行异常不中断整体流程
- 记录失败策略详情供人工排查
- 设置告警通知
- 保留历史信号作为备选

### 风险2: 风控参数过严导致大量信号被拒绝

**影响**: 信号通过率过低，交易机会减少

**概率**: 中

**缓解措施**:
- 初期使用保守参数，逐步优化
- 监控风控拒绝原因分布
- 提供配置调整接口
- 每周review风控参数合理性

### 风险3: 订单创建失败导致信号未执行

**影响**: 信号通过风控但未转化为订单

**概率**: 低

**缓解措施**:
- 订单创建前再次验证资金和持仓
- 记录失败原因供人工处理
- 支持手动重试失败订单
- 设置告警通知

### 风险4: 定时任务未触发或执行超时

**影响**: 当日信号执行流程未运行

**概率**: 低

**缓解措施**:
- 监控定时任务执行状态
- 设置执行超时告警（> 5分钟）
- 提供手动触发接口
- 每日16:00检查执行记录

### 风险5: 数据库性能问题导致执行缓慢

**影响**: 执行耗时过长，影响用户体验

**概率**: 低

**缓解措施**:
- 批量查询优化，避免N+1问题
- 添加必要的数据库索引
- 监控执行耗时
- 设置性能告警阈值

## 未来优化方向

### 短期优化（1-3个月）

1. **智能仓位管理**
   - 根据策略历史表现动态调整仓位
   - 根据市场波动率调整仓位上限
   - 实现Kelly公式仓位计算

2. **风控规则优化**
   - 收集风控拒绝数据，分析合理性
   - 根据回测结果调整参数
   - 支持策略级别的风控配置

3. **执行效率提升**
   - 并行处理独立信号
   - 优化数据库查询
   - 缓存常用数据（股票信息、持仓）

### 中期优化（3-6个月）

1. **多模式支持**
   - 支持半自动模式（人工审批）
   - 支持实时触发模式（盘中信号）
   - 支持回测模式（历史数据验证）

2. **智能执行**
   - 根据订单金额自动选择执行方式（限价/市价/算法）
   - 支持TWAP/VWAP算法交易
   - 支持分批建仓/减仓

3. **风险归因分析**
   - 分析每笔交易的风险来源
   - 计算组合风险敞口
   - 提供风险预警

### 长期优化（6-12个月）

1. **机器学习增强**
   - 使用ML模型预测信号质量
   - 自动学习最优风控参数
   - 智能止损止盈

2. **多市场支持**
   - 支持港股、美股
   - 支持期货、期权
   - 统一的风控框架

3. **分布式执行**
   - 支持多实例并行执行
   - 分布式锁避免重复执行
   - 负载均衡

## 总结

本设计方案建立了完整的"信号生成 → 风控检查 → 订单创建"自动化链路，解决了系统中17,253个信号无法执行的核心问题。

**核心特性**:
1. ✅ 全自动执行，无需人工干预
2. ✅ 每天15:30定时触发，符合A股交易节奏
3. ✅ 标准风控检查，7项检查确保交易安全
4. ✅ 限价单执行，价格可控
5. ✅ 失败记录并跳过，不阻塞整体流程
6. ✅ 完整的日志和监控，可追溯可审计

**技术亮点**:
- 集中式调度器架构，易于维护和监控
- 批量处理优化，性能高效
- 灵活的风控配置，支持动态调整
- 完善的API接口，支持手动触发和查询
- Agent工具集成，提升用户体验

**预期效果**:
- 信号执行率：从0% → 100%
- 策略运行率：从0/36 → 36/36
- 日均订单数：预计100-150个
- 执行耗时：< 2秒（处理150个信号）

**下一步**:
1. Review设计文档
2. 编写实现计划
3. 开发核心组件
4. 单元测试
5. 集成测试
6. 上线部署
7. 监控优化

---

**设计完成日期**: 2026-05-28  
**预计开发周期**: 3-5天  
**预计上线日期**: 2026-06-03

