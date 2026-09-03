# 盈利引擎系统设计和自主能力体系（Autonomy 线）架构

> 完整的自主交易闭环：从数据获取、信号生成、决策执行到绩效评估和策略进化
> 
> 最后更新：2026-09-03

---

## 一、系统总览

盈利引擎和自主能力体系是 PI Investment 的**核心智能系统**，跨越三个子系统协同工作：

- **quantsys-v2**：Python 后端，负责数据、计算、回测、执行
- **agent-os**：Go 中间件，负责决策协调、事件分发、状态管理
- **agent-ts**：TypeScript AI Agent，负责智能决策、学习进化

```
┌─────────────────────────────────────────────────────────────────┐
│                   盈利引擎 & 自主能力体系架构                      │
└─────────────────────────────────────────────────────────────────┘

                      ┌─────────────┐
                      │  Human User │
                      │  (监督者)    │
                      └──────┬──────┘
                             │ 监控/干预
                             ↓
    ┌────────────────────────────────────────────────────┐
    │              agent-ts (AI 决策大脑)                 │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Intelligence Services                        │  │
    │  │  • EvolutionService (进化决策)                │  │
    │  │  • EvolutionExecutor (参数优化执行器)         │  │
    │  │  • EvolutionScorer (适应度评分)               │  │
    │  │  • DecisionLogger (决策日志)                  │  │
    │  └──────────────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Quantsys Tools (60+ 工具)                    │  │
    │  │  • pool_manage (股票池管理)                   │  │
    │  │  • signal_scan (信号扫描)                     │  │
    │  │  • trade_execute (交易执行)                   │  │
    │  │  • backtest_run (回测执行)                    │  │
    │  └──────────────────────────────────────────────┘  │
    └────────────────┬──────────────┬────────────────────┘
                     │ HTTP API     │ WebSocket
                     ↓              ↓
    ┌────────────────────────────────────────────────────┐
    │           agent-os (决策协调中枢)                   │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  API Handlers (Go)                           │  │
    │  │  • EvolutionHandler (进化任务协调)            │  │
    │  │  • DecisionHandler (决策记录与查询)           │  │
    │  │  • NotificationHandler (通知路由)             │  │
    │  └──────────────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Domain Services                             │  │
    │  │  • DecisionService (决策生命周期管理)         │  │
    │  │  • EvolutionCoordinator (进化流程协调)        │  │
    │  │  • EventBus (事件分发)                        │  │
    │  └──────────────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Repositories (PostgreSQL)                   │  │
    │  │  • DecisionRepository (决策持久化)            │  │
    │  │  • EvolutionWebRepository (进化记录)          │  │
    │  └──────────────────────────────────────────────┘  │
    └────────────────┬────────────────┬─────────────────┘
                     │ HTTP API       │ WebSocket
                     ↓                ↓
    ┌────────────────────────────────────────────────────┐
    │        quantsys-v2 (数据与计算引擎)                 │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Evolution Services (进化引擎)                │  │
    │  │  • EvolutionFitnessService (适应度计算)       │  │
    │  │  • DecisionScoreService (决策打分)            │  │
    │  │  • MissedOpportunityService (踏空捕获)        │  │
    │  │  • DailySnapshotService (每日快照)            │  │
    │  └──────────────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Autonomy Services (自主能力)                 │  │
    │  │  • DailyOrchestrator (日常编排器)             │  │
    │  │  • SchedulerTasks (54+调度任务)               │  │
    │  │  • WatchEngine (实时盯盘引擎)                 │  │
    │  │  • SignalExecutionScheduler (信号执行调度)    │  │
    │  │  • AgentNotificationService (Agent唤醒)       │  │
    │  └──────────────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Core Services (核心服务)                     │  │
    │  │  • AccountTradingService (多账户交易)         │  │
    │  │  • BacktestService (回测引擎)                 │  │
    │  │  • ChanService (缠论分析)                     │  │
    │  │  • DataProviders (多数据源)                   │  │
    │  └──────────────────────────────────────────────┘  │
    │  ┌──────────────────────────────────────────────┐  │
    │  │  Repositories & ORM (数据持久化)              │  │
    │  │  • EvolutionFitnessRepository                │  │
    │  │  • AgentIntelligenceRepository (决策表)       │  │
    │  │  • SimulationRepository (模拟账户)            │  │
    │  │  • SignalRepository (信号表)                  │  │
    │  └──────────────────────────────────────────────┘  │
    └────────────────────┬───────────────────────────────┘
                         │
                         ↓
              ┌──────────────────┐
              │   PostgreSQL     │
              │  (主数据库)       │
              │                  │
              │  Tables:         │
              │  • agent_decisions│
              │  • evolution_fitness│
              │  • simulation_*   │
              │  • signals        │
              │  • daily_klines   │
              │  • watch_rules    │
              └──────────────────┘
```

---

## 二、三个系统的职责划分

### 2.1 quantsys-v2 (Python) - 数据与计算引擎

**技术栈**：Python 3.13 + FastAPI + SQLAlchemy + Polars

**核心职责**：
1. **数据层**：多数据源管理、K线存储、财报抓取、市场数据
2. **计算引擎**：回测、因子计算、缠论分析、风险评估
3. **执行层**：模拟交易、订单管理、持仓跟踪
4. **进化引擎**：适应度计算、决策打分、踏空捕获
5. **调度系统**：54+个定时任务、日常编排器、盯盘引擎

**DDD 架构**（分层 DDD）：
```
quantsys-v2/
├── domain/                  # 领域层（纯业务逻辑）
│   ├── accounts/           # 多账户聚合根
│   ├── strategies/         # 策略领域模型
│   ├── trading/            # 交易领域
│   ├── risk/               # 风险管理
│   └── ...
├── application/            # 应用层（用例编排）
│   ├── services/
│   │   ├── evolution/     # 进化服务
│   │   ├── daily_orchestrator.py  # 日常编排
│   │   └── scheduler_tasks.py     # 调度任务
│   └── jobs/              # 后台任务
└── adapters/              # 适配器层（I/O）
    ├── inbound/
    │   └── fastapi_app/   # HTTP API (端口5001)
    └── outbound/
        ├── repositories/  # 数据库
        └── datasources/   # 外部数据源
```

**关键 API 端点**：
- `GET /api/evolution/fitness` - 查询适应度
- `GET /api/decisions/{id}/score` - 查询决策评分
- `POST /api/orchestrator/tick` - 触发日常编排
- `GET /api/signals/ready` - 获取待执行信号
- `POST /api/trading/execute` - 执行交易

---

### 2.2 agent-os (Go) - 决策协调中枢

**技术栈**：Go 1.21 + Gin + GORM + PostgreSQL

**核心职责**：
1. **决策管理**：记录、查询、统计 Agent 的每个决策
2. **进化协调**：协调跨系统的策略进化流程
3. **事件分发**：接收 quantsys-v2 的通知并路由到 agent-ts
4. **状态同步**：维护 Agent 的会话状态和上下文

**DDD 架构**（六边形架构/端口适配器）：
```
agent-os/
├── internal/
│   ├── domain/              # 领域层
│   │   ├── decision.go      # 决策聚合根
│   │   ├── evolution_web.go # 进化领域模型
│   │   ├── memory.go        # 记忆
│   │   └── notification.go  # 通知
│   ├── service/             # 应用服务
│   │   ├── decision_service.go
│   │   └── evolution_coordinator.go
│   ├── api/                 # 入站适配器 (HTTP)
│   │   ├── decision_handler.go
│   │   └── evolution_handler.go
│   ├── repository/          # 出站适配器 (DB)
│   │   ├── decision_repository.go
│   │   └── evolution_web_repository.go
│   └── events/              # 事件总线
└── cmd/                     # 启动入口
```

**关键 API 端点**：
- `POST /api/v1/decisions` - 记录决策
- `GET /api/v1/decisions/{id}` - 查询决策
- `POST /api/v1/evolution/run` - 执行进化
- `GET /api/v1/evolution/leaderboard` - 进化排行榜

---

### 2.3 agent-ts (TypeScript) - AI 决策大脑

**技术栈**：TypeScript + DeepSeek V4 + Node.js

**核心职责**：
1. **智能决策**：基于 LLM 的交易决策、风险评估、策略选择
2. **工具调用**：通过 60+ 工具与 quantsys-v2 交互
3. **进化执行**：参数优化、A/B测试、策略升级决策
4. **学习反馈**：从历史决策中学习，改进提示词和策略

**架构**（工具驱动架构）：
```
agent-ts/
├── src/
│   ├── core/                # 核心引擎
│   │   ├── agent-loop.ts    # 主循环
│   │   └── session.ts       # 会话管理
│   ├── services/
│   │   ├── intelligence/    # 智能服务
│   │   │   ├── evolution-service.ts      # 进化服务
│   │   │   ├── evolution-executor.ts     # 参数优化执行
│   │   │   └── evolution-scorer.ts       # 适应度评分
│   │   ├── llm/             # LLM 抽象
│   │   └── memory/          # 记忆服务
│   ├── infrastructure/
│   │   └── tools/           # 60+ 工具
│   │       ├── pool-tools.ts
│   │       ├── signal-tools.ts
│   │       ├── trade-tools.ts
│   │       └── backtest-tools.ts
│   └── channels/            # 多通道适配
│       ├── cli/
│       ├── tui/
│       └── feishu/
```

**核心工具**：
- `pool_manage` - 股票池管理
- `signal_scan` - 信号扫描
- `trade_execute` - 交易执行
- `backtest_run` - 回测运行
- `evolution_status` - 进化状态查询

---

## 三、盈利引擎实现细节

### 3.1 双侧捕获适应度系统

**实现位置**：`quantsys-v2/application/services/evolution/evolution_fitness_service.py`

#### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│          双侧捕获适应度计算流程（每日自动运行）              │
└─────────────────────────────────────────────────────────────┘

Step 1: 数据准备 (DailySnapshotService)
  每日收盘后 (15:30)
  ↓
  记录所有模拟账户的权益快照
  ├─ total_value: 总资产
  ├─ daily_return: 当日收益率
  ├─ cash: 现金
  └─ stock_value: 持仓市值
  ↓
  写入 simulation_equity_snapshots 表

Step 2: 适应度计算 (EvolutionFitnessService)
  每日 16:30 (调度任务触发)
  ↓
  for each active account:
    1. 拉取最近45天的权益快照
    2. 拉取沪深300基准K线数据
    3. 计算滚动20交易日窗口
       ├─ 对齐日期 = 账户 ∩ 基准的共同交易日
       ├─ 筛选最近20个交易日
       └─ 分离上涨日和下跌日
    4. 计算双侧捕获
       ├─ up_capture = Σ(账户上涨日收益) / Σ(基准上涨日收益)
       ├─ down_capture = Σ(账户下跌日跌幅) / Σ(基准下跌日跌幅)
       └─ fitness = (up_capture - 1.0) * 100 - (down_capture - 1.0) * 100
    5. Upsert 到 evolution_fitness 表
       ├─ 主键: (account_name, window_end, window_days)
       └─ 幂等性: 重复运行覆盖

Step 3: 排行榜更新
  ↓
  按 fitness 降序排列所有账户
  ↓
  Web Dashboard 展示排行榜
```

#### 适应度公式

```python
# 上涨捕获率 (进攻能力)
up_capture = sum(account_return for day in up_days) / 
             sum(benchmark_return for day in up_days)

# 下跌捕获率 (防守能力)
down_capture = sum(account_return for day in down_days) / 
               sum(benchmark_return for day in down_days)

# 综合适应度 (越高越好)
fitness = (up_capture - 1.0) * 100 - (down_capture - 1.0) * 100

# 示例解读：
# up_capture = 1.2  → 上涨日赚20%超额收益 → +20分
# down_capture = 0.8 → 下跌日只亏80% → +20分
# fitness = 20 + 20 = 40分
```

#### 数据表结构

```sql
CREATE TABLE evolution_fitness (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(100) NOT NULL,
    window_end DATE NOT NULL,
    window_days INTEGER NOT NULL DEFAULT 20,
    up_capture NUMERIC(10, 4),      -- 上涨捕获率
    down_capture NUMERIC(10, 4),    -- 下跌捕获率
    fitness NUMERIC(10, 4),         -- 综合适应度
    up_days INTEGER,                 -- 上涨天数
    down_days INTEGER,               -- 下跌天数
    status VARCHAR(50),              -- 'data_gap' | 'computed'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(account_name, window_end, window_days)
);
```

---

### 3.2 决策打分系统

**实现位置**：`quantsys-v2/application/services/evolution/decision_score_service.py`

#### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│            决策打分流程（20交易日后自动打分）                 │
└─────────────────────────────────────────────────────────────┘

Step 1: Agent 做出决策
  agent-ts 调用 trade_execute 工具
  ↓
  agent-os 记录决策到 agent_decisions 表
  ├─ decision_id: UNIQUE ID
  ├─ decision_type: 'trade_buy' | 'trade_sell'
  ├─ parameters: { symbol, price, quantity }
  ├─ reasoning: LLM 输出的理由
  ├─ created_at: 决策时间
  └─ evaluation_status: 'pending'

Step 2: 等待成熟窗口
  每日 16:30 (DecisionScoreService)
  ↓
  扫描 evaluation_status='pending' 的决策
  ↓
  for each decision:
    1. 获取决策日期 trade_date
    2. 拉取后续 K 线数据
    3. 计算交易日之后的K线数量
    4. 判断成熟度
       ├─ len(future_klines) >= 20 → 成熟，可打分
       └─ len(future_klines) < 20 → 未成熟，跳过

Step 3: 计算评分 (compute_trade_score)
  成熟决策 (满20交易日)
  ↓
  ref_price = future_klines[19].close  # 第20个交易日收盘价
  trade_price = decision.parameters.price
  ↓
  计算收益率:
  ├─ stock_return = (ref_price / trade_price - 1) * direction
  │   └─ direction = +1 (buy) | -1 (sell)
  ├─ benchmark_return = (沪深300 第20日 / 第1日 - 1)
  └─ alpha = stock_return - benchmark_return
  ↓
  评分:
  ├─ score = alpha * 100  (超额收益百分比)
  └─ band = 分档
      ├─ excellent: alpha > 10%
      ├─ good: alpha > 5%
      ├─ neutral: -5% <= alpha <= 5%
      ├─ poor: -10% < alpha < -5%
      └─ bad: alpha <= -10%

Step 4: 回写评分
  ↓
  UPDATE agent_decisions SET
    evaluation_status = 'evaluated',
    evaluation_score = score,
    evaluation_band = band,
    evaluation_detail = {
      window_trading_days: 20,
      trade_date: '2026-09-03',
      ref_date: '2026-10-01',
      trade_price: 50.00,
      ref_price: 55.00,
      stock_return: 0.10,
      benchmark_return: 0.03,
      alpha: 0.07,
      score: 7.0,
      band: 'good'
    }
  WHERE decision_id = xxx
```

#### 评分示例

```python
# 买入决策案例
trade_buy = {
    'symbol': '600519',
    'trade_price': 1800.00,
    'trade_date': '2026-09-03'
}

# 20个交易日后 (2026-10-08)
ref_price = 1980.00  # 涨了10%

# 同期沪深300
benchmark_return = 0.03  # 涨了3%

# 计算
stock_return = (1980 / 1800 - 1) = 0.10 = 10%
alpha = 0.10 - 0.03 = 0.07 = 7%
score = 7.0
band = 'good'

# 卖出决策案例
trade_sell = {
    'symbol': '000001',
    'trade_price': 12.00,
    'trade_date': '2026-09-03'
}

# 20个交易日后
ref_price = 11.00  # 跌了8.3%

# 卖对了（避免了损失）
stock_return = -(11 / 12 - 1) = 0.083 = 8.3%
alpha = 0.083 - 0.03 = 0.053 = 5.3%
score = 5.3
band = 'good'
```

---

### 3.3 踏空捕获系统

**实现位置**：`quantsys-v2/application/services/evolution/missed_opportunity_service.py`

#### 设计哲学

> **"不行动也是决策，必须接受评估"**
> 
> 防止 Agent 通过"少交易"来逃避负面评分。如果 Agent 看到买入信号但选择不动，20日后如果该股票大涨，就是"踏空"，应该扣分。

#### 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│          踏空捕获流程（防止投机逃避评价）                     │
└─────────────────────────────────────────────────────────────┘

Step 1: 信号生成
  策略 (v13/v14/v15) 生成买入信号
  ↓
  写入 signals 表
  ├─ signal_id: UNIQUE ID
  ├─ action: 'buy'
  ├─ symbol: '600519'
  ├─ price: 1800.00
  ├─ signal_date: '2026-09-03'
  ├─ status: 'pending'  (等待Agent决策)
  └─ strategy_id: 'v13'

Step 2: Agent 决策
  Agent 收到 signals_ready 通知
  ↓
  Agent 查看信号后选择:
  ├─ 情况A: 执行买入 → status='executed'
  ├─ 情况B: 明确拒绝 → status='rejected'
  └─ 情况C: 无反应 → status='pending'

Step 3: 踏空扫描 (MissedOpportunityService)
  每日 16:30 运行
  ↓
  扫描过去10天的 pending/rejected 买入信号
  ↓
  for each signal:
    1. 检查宽限期 (5个交易日)
       ├─ 拉取 signal_date 之后的 K 线
       └─ len(future_klines) >= 5 → 进入候选
    2. 检查是否已行动
       └─ 查询 agent_decisions 表
           ├─ 宽限期内有 trade_buy(symbol) → 已行动，跳过
           └─ 没有 → 确认踏空
    3. 创建 missed_opportunity 决策
       └─ INSERT INTO agent_decisions {
             decision_id: 'MISS-{signal_id}',
             decision_type: 'missed_opportunity',
             context: {
               source: 'missed_signal_capture',
               strategy_id: 'v13',
               signal_status: 'pending',
               signal_date: '2026-09-03'
             },
             parameters: { symbol, price, signal_id },
             reasoning: '信号未行动捕获(v13 @ 2026-09-03)',
             created_at: signal_date,
             evaluation_status: 'pending'
           }

Step 4: 延迟打分 (DecisionScoreService)
  20个交易日后
  ↓
  对 missed_opportunity 决策打分:
  ├─ 信号后股票涨 → 负分 (踏空了赚钱机会)
  ├─ 信号后股票跌 → 正分 (正确观望，避免了损失)
  └─ 评分逻辑与 trade_buy 相同
```

#### 防御机制

```python
# 每日限量 (防止刷屏)
daily_cap = 5  # 每天最多捕获5个踏空

# 置信度优先
同一天有多个信号 → 按 confidence 降序取前5个

# 宽限期 (给Agent充分决策时间)
grace_trading_days = 5  # 5个交易日内行动不算踏空

# 去重 (防止重复捕获)
decision_id = f"MISS-{signal_id}"  # 已捕获的不会再创建
```

---

## 四、自主能力体系实现细节

### 4.1 日常投资循环编排器

**实现位置**：`quantsys-v2/application/services/daily_orchestrator.py`

#### 状态机设计

```
┌─────────────────────────────────────────────────────────────┐
│                  日常投资循环状态机                           │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────┐
                    │   IDLE   │ (非交易时段)
                    └────┬─────┘
                         │ 08:30 到达
                         ↓
                  ┌─────────────┐
                  │ PRE_MARKET  │ (盘前准备)
                  │ 08:30-09:25 │
                  └──────┬──────┘
                         │ • 股票池刷新
                         │ • 策略信号生成
                         │ • 缠论扫描
                         │ • Agent 收到 signals_ready 通知
                         ↓
                  ┌─────────────┐
                  │ MARKET_OPEN │ (开盘确认)
                  │ 09:25-09:35 │
                  └──────┬──────┘
                         │ • 最后确认
                         │ • 风险检查
                         ↓
                  ┌─────────────┐
                  │  INTRADAY   │ (盘中监控)
                  │ 09:35-15:00 │
                  └──────┬──────┘
                         │ • WatchEngine 实时盯盘
                         │ • 触发条件 → 唤醒 Agent
                         │ • Agent 决策 → 立即执行
                         ↓
                  ┌─────────────┐
                  │MARKET_CLOSE │ (收盘捕获)
                  │ 15:00-15:05 │
                  └──────┬──────┘
                         │ • 捕获收盘价
                         │ • 冻结当日K线
                         ↓
                  ┌─────────────┐
                  │ POST_MARKET │ (盘后处理)
                  │ 15:30-16:30 │
                  └──────┬──────┘
                         │ • 执行待处理信号
                         │ • 更新持仓
                         │ • 权益快照
                         ↓
                  ┌─────────────┐
                  │   REVIEW    │ (复盘进化)
                  │ 16:30-17:30 │
                  └──────┬──────┘
                         │ • 决策打分 (20日成熟)
                         │ • 踏空捕获 (5日宽限)
                         │ • 适应度计算 (20日窗口)
                         │ • Agent 收到绩效报告
                         ↓
                    ┌──────────┐
                    │   IDLE   │ (回到休息)
                    └──────────┘
```

#### 实现代码结构

```python
class DailyOrchestrator:
    def __init__(self, name='main'):
        self.name = name
        self._today_state = None  # 从 DB 加载
    
    def tick(self):
        """APScheduler 每分钟调用一次"""
        now = datetime.now()
        
        # 1. 加载或创建今日状态
        state = self._get_or_create_state(date.today())
        
        # 2. 判断当前应处于哪个阶段
        target_phase = self._determine_phase(now.time())
        
        # 3. 如果需要切换阶段
        if state.current_phase != target_phase:
            self._transition(state, target_phase)
        
        # 4. 执行当前阶段任务
        self._execute_phase_tasks(state, target_phase)
    
    def _transition(self, state, new_phase):
        """阶段切换"""
        old = state.current_phase
        logger.info(f"Phase transition: {old} → {new_phase}")
        
        # 调用阶段退出钩子
        self._on_phase_exit(old)
        
        # 更新状态
        state.current_phase = new_phase
        state.phase_changed_at = datetime.now()
        self.session.commit()
        
        # 调用阶段进入钩子
        self._on_phase_enter(new_phase)
        
        # 通知 Agent
        agent_service.notify_phase_change(new_phase)
    
    def _execute_phase_tasks(self, state, phase):
        """执行阶段任务"""
        tasks = {
            Phase.PRE_MARKET: self._pre_market_tasks,
            Phase.MARKET_OPEN: self._market_open_tasks,
            Phase.INTRADAY: self._intraday_tasks,
            Phase.MARKET_CLOSE: self._market_close_tasks,
            Phase.POST_MARKET: self._post_market_tasks,
            Phase.REVIEW: self._review_tasks,
        }
        
        task_fn = tasks.get(phase)
        if task_fn:
            task_fn(state)
    
    def _review_tasks(self, state):
        """复盘阶段任务"""
        if state.review_completed:
            return  # 已完成，不重复执行
        
        # 1. 决策打分
        DecisionScoreService().score_mature_decisions(pending_days=30)
        
        # 2. 踏空捕获
        MissedOpportunityService().capture(lookback_days=10)
        
        # 3. 适应度计算
        EvolutionFitnessService().compute_all_accounts()
        
        # 4. 每日快照
        DailySnapshotService().snapshot_all_accounts()
        
        # 标记完成
        state.review_completed = True
        self.session.commit()
        
        # 通知 Agent
        agent_service.notify_daily_report_ready(date.today())
```

#### 状态持久化

```sql
CREATE TABLE daily_orchestrator_states (
    id SERIAL PRIMARY KEY,
    orchestrator_name VARCHAR(50) NOT NULL,
    trading_date DATE NOT NULL,
    current_phase VARCHAR(20) NOT NULL,
    phase_changed_at TIMESTAMP,
    pre_market_completed BOOLEAN DEFAULT FALSE,
    market_open_completed BOOLEAN DEFAULT FALSE,
    intraday_completed BOOLEAN DEFAULT FALSE,
    market_close_completed BOOLEAN DEFAULT FALSE,
    post_market_completed BOOLEAN DEFAULT FALSE,
    review_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(orchestrator_name, trading_date)
);
```

---

### 4.2 调度任务系统

**实现位置**：`quantsys-v2/application/services/scheduler_tasks.py`

#### 任务注册表

```python
# 54+ 个注册任务（截至2026-09）
SCHEDULED_TASKS = {
    # ============ 数据更新任务 ============
    'kline_update_job': {
        'cron': '40 17 * * 1-5',  # 每个交易日 17:40
        'function': kline_update_job,
        'description': 'K线数据更新（日线）',
        'timeout': 600,
    },
    'financial_statement_update': {
        'cron': '0 20 * * 6',  # 每周六 20:00
        'function': update_financial_statements,
        'description': '财报数据更新',
        'timeout': 1800,
    },
    'chip_distribution_daily': {
        'cron': '0 18 * * 1-5',  # 每个交易日 18:00
        'function': compute_chip_distribution,
        'description': '筹码分布计算',
        'timeout': 900,
    },
    'fund_flow_update': {
        'cron': '30 15 * * 1-5',  # 每个交易日 15:30
        'function': update_fund_flow_data,
        'description': '资金流数据更新',
        'timeout': 300,
    },
    
    # ============ 信号生成任务 ============
    'pool_refresh_daily': {
        'cron': '0 8 * * 1-5',  # 每个交易日 08:00
        'function': refresh_stock_pools,
        'description': '股票池每日刷新',
        'timeout': 300,
    },
    'chan_daily_scan': {
        'cron': '30 8 * * 1-5',  # 每个交易日 08:30
        'function': scan_chan_patterns,
        'description': '缠论形态扫描',
        'timeout': 600,
    },
    'strategy_signal_generation': {
        'cron': '0 9 * * 1-5',  # 每个交易日 09:00
        'function': generate_strategy_signals,
        'description': '策略信号生成',
        'timeout': 300,
    },
    
    # ============ 进化引擎任务 ============
    'evolution_fitness_daily': {
        'cron': '30 16 * * 1-5',  # 每个交易日 16:30
        'function': compute_evolution_fitness,
        'description': '适应度计算',
        'timeout': 600,
    },
    'decision_score_daily': {
        'cron': '45 16 * * 1-5',  # 每个交易日 16:45
        'function': score_mature_decisions,
        'description': '决策打分',
        'timeout': 300,
    },
    'missed_opportunity_capture': {
        'cron': '0 17 * * 1-5',  # 每个交易日 17:00
        'function': capture_missed_opportunities,
        'description': '踏空捕获',
        'timeout': 300,
    },
    'daily_snapshot': {
        'cron': '15 16 * * 1-5',  # 每个交易日 16:15
        'function': snapshot_all_accounts,
        'description': '每日权益快照',
        'timeout': 180,
    },
    
    # ============ 监控告警任务 ============
    'data_quality_check': {
        'cron': '0 18 * * 1-5',  # 每个交易日 18:00
        'function': check_data_quality,
        'description': '数据质量检查',
        'timeout': 300,
    },
    'circuit_breaker_monitor': {
        'cron': '*/5 9-15 * * 1-5',  # 盘中每5分钟
        'function': monitor_circuit_breaker,
        'description': '熔断监控',
        'timeout': 60,
    },
    
    # ============ 日常编排任务 ============
    'orchestrator_tick': {
        'cron': '* 8-18 * * 1-5',  # 盘中每分钟
        'function': daily_orchestrator_tick,
        'description': '日常编排器心跳',
        'timeout': 60,
    },
}
```

#### 任务执行框架

```python
class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler(
            timezone='Asia/Shanghai',
            job_defaults={
                'coalesce': True,  # 合并错过的任务
                'max_instances': 1,  # 同一任务不并发
                'misfire_grace_time': 300,  # 5分钟宽限
            }
        )
    
    def register_all_tasks(self):
        """注册所有任务"""
        for task_id, config in SCHEDULED_TASKS.items():
            self.register_task(task_id, config)
    
    def register_task(self, task_id, config):
        """注册单个任务"""
        self.scheduler.add_job(
            func=self._wrapped_task(config['function']),
            trigger='cron',
            **self._parse_cron(config['cron']),
            id=task_id,
            name=config['description'],
            replace_existing=True,
        )
        logger.info(f"Registered task: {task_id}")
    
    def _wrapped_task(self, task_fn):
        """任务包装器（日志、异常处理、超时）"""
        def wrapper():
            task_name = task_fn.__name__
            start_time = time.time()
            
            try:
                logger.info(f"Task started: {task_name}")
                result = task_fn()
                elapsed = time.time() - start_time
                logger.info(f"Task completed: {task_name} ({elapsed:.2f}s)")
                
                # 记录任务执行历史
                self._log_task_run(task_name, 'success', elapsed, result)
                
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"Task failed: {task_name}", exc_info=True)
                
                # 记录失败
                self._log_task_run(task_name, 'failed', elapsed, str(e))
                
                # 告警
                self._alert_task_failure(task_name, e)
        
        return wrapper
    
    def start(self):
        """启动调度器"""
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown()
        logger.info("Scheduler shutdown")
```

---

### 4.3 盯盘引擎 (Watch Engine)

**实现位置**：`quantsys-v2/domain/watch/` + `watch_rules` 表

#### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                   实时盯盘引擎架构                            │
└─────────────────────────────────────────────────────────────┘

            ┌──────────────┐
            │  watch_rules │ (PostgreSQL)
            │  (盯盘规则表) │
            └───────┬──────┘
                    │ 加载规则
                    ↓
         ┌────────────────────┐
         │   WatchEngine      │
         │  (规则执行引擎)     │
         └─────────┬──────────┘
                   │ 每分钟扫描 (盘中)
                   ↓
         ┌────────────────────┐
         │  实时市场数据       │
         │  • 涨跌幅          │
         │  • 成交量          │
         │  • 换手率          │
         │  • 技术指标        │
         └─────────┬──────────┘
                   │ 规则匹配
                   ↓
            触发条件满足？
            ├─ 否 → 继续监控
            └─ 是 ↓
         ┌────────────────────┐
         │ AgentNotification  │
         │   Service          │
         └─────────┬──────────┘
                   │ WebSocket / HTTP
                   ↓
         ┌────────────────────┐
         │    agent-os        │
         │  (事件路由)         │
         └─────────┬──────────┘
                   │ 推送
                   ↓
         ┌────────────────────┐
         │    agent-ts        │
         │  (Agent 决策)       │
         └────────────────────┘
```

#### 规则表结构

```sql
CREATE TABLE watch_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    condition_type VARCHAR(50) NOT NULL,  -- 'price_change' | 'volume_spike' | 'technical'
    condition_params JSONB NOT NULL,
    target_symbols TEXT[],  -- NULL = 全市场
    action_type VARCHAR(50) NOT NULL,  -- 'notify_agent' | 'auto_execute'
    action_params JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 示例规则
INSERT INTO watch_rules (rule_name, condition_type, condition_params, action_type) VALUES
-- 涨停板监控
('limit_up_watch', 'price_change', 
 '{"threshold": 9.9, "direction": "up", "duration_minutes": 1}',
 'notify_agent'),

-- 跌停板监控  
('limit_down_watch', 'price_change',
 '{"threshold": -9.9, "direction": "down", "duration_minutes": 1}',
 'notify_agent'),

-- 成交量异常
('volume_spike', 'volume_spike',
 '{"multiplier": 3.0, "baseline_days": 5}',
 'notify_agent'),

-- 技术形态
('macd_golden_cross', 'technical',
 '{"indicator": "macd", "pattern": "golden_cross"}',
 'notify_agent');
```

#### 实现代码

```python
class WatchEngine:
    def __init__(self):
        self.rules = self._load_rules()
        self.market_data_cache = {}
    
    def scan(self):
        """盘中每分钟调用一次"""
        if not self._is_trading_time():
            return
        
        # 1. 更新市场数据缓存
        self._update_market_data()
        
        # 2. 执行所有启用的规则
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                self._execute_rule(rule)
            except Exception as e:
                logger.error(f"Rule execution failed: {rule.rule_name}", exc_info=True)
    
    def _execute_rule(self, rule):
        """执行单条规则"""
        # 1. 获取监控标的（全市场或指定股票）
        symbols = rule.target_symbols or self._get_all_symbols()
        
        # 2. 对每个标的检查条件
        for symbol in symbols:
            if self._check_condition(rule, symbol):
                # 触发！
                self._trigger_action(rule, symbol)
    
    def _check_condition(self, rule, symbol):
        """检查触发条件"""
        data = self.market_data_cache.get(symbol)
        if not data:
            return False
        
        if rule.condition_type == 'price_change':
            # 涨跌幅条件
            threshold = rule.condition_params['threshold']
            direction = rule.condition_params.get('direction', 'both')
            pct_change = data['pct_change']
            
            if direction == 'up':
                return pct_change >= threshold
            elif direction == 'down':
                return pct_change <= threshold
            else:
                return abs(pct_change) >= abs(threshold)
        
        elif rule.condition_type == 'volume_spike':
            # 成交量异常
            multiplier = rule.condition_params['multiplier']
            baseline_days = rule.condition_params['baseline_days']
            
            recent_volume = data['volume']
            avg_volume = self._get_avg_volume(symbol, baseline_days)
            
            return recent_volume >= avg_volume * multiplier
        
        elif rule.condition_type == 'technical':
            # 技术指标
            indicator = rule.condition_params['indicator']
            pattern = rule.condition_params['pattern']
            
            return self._check_technical_pattern(symbol, indicator, pattern)
        
        return False
    
    def _trigger_action(self, rule, symbol):
        """触发动作"""
        logger.info(f"Watch rule triggered: {rule.rule_name} on {symbol}")
        
        if rule.action_type == 'notify_agent':
            # 唤醒 Agent
            agent_service.notify_watch_triggered(
                rule_name=rule.rule_name,
                symbol=symbol,
                market_data=self.market_data_cache[symbol],
                suggestion=rule.action_params.get('suggestion', '')
            )
        
        elif rule.action_type == 'auto_execute':
            # 自动执行（高风险，慎用）
            self._auto_execute_trade(rule, symbol)
        
        # 记录触发历史
        self._log_trigger(rule, symbol)
```

---

## 五、完整闭环流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│              盈利引擎 & 自主能力体系完整闭环流程图                        │
└─────────────────────────────────────────────────────────────────────────┘

时间线                  quantsys-v2                agent-os              agent-ts
────────────────────────────────────────────────────────────────────────────

每日 00:00-08:00
数据准备阶段
                  ┌─────────────────┐
                  │ SchedulerTasks  │
                  │ • kline_update  │
                  │ • fund_flow     │
                  │ • chip_dist     │
                  └─────────────────┘

每日 08:30-09:25
PRE_MARKET 阶段
                  ┌─────────────────┐
                  │DailyOrchestrator│
                  │ Phase Transition│
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ pool_refresh    │
                  │ chan_scan       │
                  │ signal_generate │
                  └────────┬────────┘
                           │ signals_ready
                           ├──────────────┐
                           │              │
                           │         ┌────▼────┐
                           │         │ Notify  │
                           │         │ Event   │
                           │         └────┬────┘
                           │              │
                           │         ┌────▼────────┐
                           │         │ Agent Loop  │
                           │         │ 收到通知     │
                           │         └────┬────────┘
                           │              │
                           │              │ 调用工具
                           │         ┌────▼────────┐
                           │         │signal_scan  │
                           │         │查看信号      │
                           │         └────┬────────┘
                           │              │
                           │              │ LLM 决策
                           │         ┌────▼────────┐
                           │         │ 决策输出:    │
                           │         │ BUY 600519  │
                           │         │ @ 1800.00   │
                           │         └────┬────────┘
                           │              │
                           │              │ 调用工具
                           │         ┌────▼────────┐
                           │         │trade_execute│
                           │         └────┬────────┘
                           │              │
                  ┌────────▼──────────────▼─────┐
                  │ HTTP POST                   │
                  │ /api/trading/execute        │
                  └────────┬────────────────────┘
                           │
                  ┌────────▼────────┐      ┌─────────────┐
                  │AccountTradingService│   │Decision     │
                  │执行交易              │──▶│Repository   │
                  └─────────────────────┘   └──────┬──────┘
                                                   │
                                            ┌──────▼──────┐
                                            │ agent_      │
                                            │ decisions   │
                                            │ INSERT      │
                                            └─────────────┘

每日 09:25-15:00
INTRADAY 阶段
                  ┌─────────────────┐
                  │  WatchEngine    │
                  │  实时盯盘       │
                  └────────┬────────┘
                           │ 每分钟扫描
                           │
                  ┌────────▼────────┐
                  │ 条件触发？      │
                  │ • 涨停板       │
                  │ • 成交量异常    │
                  └────────┬────────┘
                           │ watch_triggered
                           ├──────────────┐
                           │              │
                           │         ┌────▼────┐
                           │         │ Notify  │
                           │         └────┬────┘
                           │              │
                           │         ┌────▼────────┐
                           │         │ Agent 决策  │
                           │         │ (同上流程)  │
                           │         └─────────────┘

每日 15:30-16:30
POST_MARKET 阶段
                  ┌─────────────────┐
                  │SignalExecution  │
                  │Scheduler        │
                  │执行pending信号  │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 更新持仓        │
                  │ simulation_     │
                  │ holdings        │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │DailySnapshot    │
                  │Service          │
                  │权益快照         │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │simulation_      │
                  │equity_snapshots │
                  │INSERT           │
                  └─────────────────┘

每日 16:30-17:30
REVIEW 阶段
(进化引擎核心)
                  ┌─────────────────┐
                  │MissedOpportunity│
                  │Service          │
                  └────────┬────────┘
                           │ 扫描未行动信号
                  ┌────────▼────────┐
                  │ 创建 missed_    │
                  │ opportunity决策 │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐      ┌─────────────┐
                  │DecisionScore    │      │ agent_      │
                  │Service          │─────▶│ decisions   │
                  └────────┬────────┘      │ UPDATE      │
                           │               │ evaluation_ │
                           │               │ score/band  │
                  ┌────────▼────────┐      └─────────────┘
                  │ 扫描pending决策  │
                  │ 满20交易日？    │
                  └────────┬────────┘
                           │ 成熟决策
                  ┌────────▼────────┐
                  │ 拉取K线数据     │
                  │ 计算ref_price   │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 计算超额收益    │
                  │ alpha = stock - │
                  │ benchmark       │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 评分分档        │
                  │ excellent/good/ │
                  │ neutral/poor/bad│
                  └────────┬────────┘
                           │
                           │ 回写评分
                  ┌────────▼────────┐
                  │ UPDATE agent_   │
                  │ decisions SET   │
                  │ evaluation_     │
                  │ status='evaluated'│
                  └─────────────────┘
                           │
                  ┌────────▼────────┐
                  │EvolutionFitness │
                  │Service          │
                  └────────┬────────┘
                           │ 计算适应度
                  ┌────────▼────────┐
                  │ 拉取权益快照    │
                  │ 拉取沪深300K线 │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 对齐日期        │
                  │ 滚动20交易日    │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 分离上涨/下跌日 │
                  │ up_capture      │
                  │ down_capture    │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 计算fitness     │
                  │ = (up-1)*100 -  │
                  │   (down-1)*100  │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ UPSERT evolution│
                  │ _fitness        │
                  └────────┬────────┘
                           │
                           │ daily_report_ready
                           ├──────────────┐
                           │              │
                           │         ┌────▼────┐
                           │         │ Notify  │
                           │         └────┬────┘
                           │              │
                           │         ┌────▼────────┐
                           │         │ Agent 接收  │
                           │         │ 绩效报告    │
                           │         └────┬────────┘
                           │              │
                           │              │ LLM 分析
                           │         ┌────▼────────┐
                           │         │ 复盘思考:    │
                           │         │ • 今日表现   │
                           │         │ • 决策质量   │
                           │         │ • 改进方向   │
                           │         └─────────────┘

每周/每月
长周期进化
                  ┌─────────────────┐
                  │EvolutionService │
                  │(agent-ts)       │
                  └────────┬────────┘
                           │
                           │ HTTP POST
                  ┌────────▼────────┐      ┌─────────────┐
                  │/api/v1/evolution│      │Evolution    │
                  │/run             │─────▶│Handler      │
                  └─────────────────┘      │(agent-os)   │
                                           └──────┬──────┘
                                                  │
                                           ┌──────▼──────┐
                                           │ 拉取quantsys│
                                           │ 基线表现    │
                                           └──────┬──────┘
                                                  │
                                           ┌──────▼──────┐
                                           │ 生成参数变体 │
                                           │ risk_multi  │
                                           │ 0.85→1.30   │
                                           └──────┬──────┘
                                                  │
                  ┌────────────────────────────▼──┐
                  │ HTTP POST                     │
                  │ /api/backtest/strategy        │
                  │ (for each variant)            │
                  └────────┬──────────────────────┘
                           │
                  ┌────────▼────────┐
                  │BacktestService  │
                  │执行回测          │
                  └────────┬────────┘
                           │
                           │ 回测结果
                  ┌────────▼────────┐
                  │ 选出最优变体    │
                  │ max(fitness)    │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐      ┌─────────────┐
                  │ 写入进化记录    │──────▶│ evolution_  │
                  └─────────────────┘      │ runs        │
                                           └─────────────┘
                           │
                           │ evolution_complete
                           ├──────────────┐
                           │              │
                           │         ┌────▼────┐
                           │         │ Agent   │
                           │         │ 决定是否 │
                           │         │ 升级策略 │
                           │         └─────────┘

────────────────────────────────────────────────────────────────────────────
```

---

## 六、关键技术点

### 6.1 分布式 DDD 集成

```
┌─────────────────────────────────────────────────────────────┐
│                分布式 DDD 限界上下文划分                      │
└─────────────────────────────────────────────────────────────┘

quantsys-v2 限界上下文:
├─ Trading Context (交易上下文)
│  ├─ 聚合根: Account, Position, Trade
│  └─ 职责: 订单管理、持仓跟踪、资金清算
├─ Evolution Context (进化上下文)
│  ├─ 聚合根: Fitness, Decision, EvolutionRun
│  └─ 职责: 适应度计算、决策评分、进化记录
├─ Strategy Context (策略上下文)
│  ├─ 聚合根: Strategy, Signal, Backtest
│  └─ 职责: 策略配置、信号生成、回测执行
└─ Data Context (数据上下文)
   ├─ 聚合根: Kline, Financial, MarketData
   └─ 职责: 数据获取、清洗、存储

agent-os 限界上下文:
├─ Decision Context (决策上下文)
│  ├─ 聚合根: Decision
│  └─ 职责: 决策记录、查询、统计
├─ Evolution Context (进化上下文)
│  ├─ 聚合根: EvolutionRun
│  └─ 职责: 进化协调、排行榜
└─ Notification Context (通知上下文)
   ├─ 聚合根: Notification
   └─ 职责: 事件路由、WebSocket推送

agent-ts 限界上下文:
├─ Intelligence Context (智能上下文)
│  ├─ 聚合根: AgentSession
│  └─ 职责: LLM决策、工具调用、学习反馈
└─ Memory Context (记忆上下文)
   ├─ 聚合根: Memory
   └─ 职责: 长期记忆、经验检索

跨上下文集成方式:
├─ RESTful API (HTTP)
├─ WebSocket (实时推送)
└─ 事件总线 (异步解耦)
```

### 6.2 事件驱动架构

```python
# quantsys-v2 发布事件
class AgentNotificationService:
    def notify_signals_ready(self, signals):
        event = {
            'type': 'signals_ready',
            'data': {'signals': signals},
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. WebSocket 推送（实时）
        self.websocket_server.broadcast(event)
        
        # 2. HTTP 回调 agent-os（持久）
        requests.post(
            f"{AGENT_OS_URL}/api/v1/notifications",
            json=event
        )

# agent-os 路由事件
class NotificationHandler:
    def handle_event(self, event):
        event_type = event['type']
        
        if event_type == 'signals_ready':
            # 路由到 agent-ts
            self.forward_to_agent(event)
        elif event_type == 'watch_triggered':
            self.forward_to_agent(event)
        elif event_type == 'daily_report_ready':
            self.forward_to_agent(event)

# agent-ts 接收事件
class AgentLoop:
    async def handle_notification(self, event):
        event_type = event['type']
        
        if event_type == 'signals_ready':
            # 唤醒 Agent 查看信号
            await self.run_skill('signal_review')
        elif event_type == 'watch_triggered':
            # 紧急决策
            await self.run_skill('intraday_decision')
```

### 6.3 数据一致性保证

```python
# quantsys-v2 → agent-os 决策同步
class AccountTradingService:
    def execute_trade(self, trade_request):
        # 1. 本地执行交易
        trade = self._execute_simulation_trade(trade_request)
        
        # 2. 同步到 agent-os (双写)
        try:
            decision = {
                'decision_id': trade.trade_id,
                'decision_type': f"trade_{trade.action}",
                'parameters': {
                    'symbol': trade.symbol,
                    'price': trade.price,
                    'quantity': trade.quantity
                },
                'reasoning': trade_request.get('reasoning', ''),
                'created_at': trade.trade_date.isoformat(),
                'evaluation_status': 'pending'
            }
            
            requests.post(
                f"{AGENT_OS_URL}/api/v1/decisions",
                json=decision,
                timeout=5
            )
        except Exception as e:
            # 失败不回滚（最终一致性）
            logger.error(f"Decision sync failed: {e}")
            # 后台补偿任务会重试
        
        return trade

# 补偿任务（保证最终一致性）
class DecisionSyncJob:
    def run(self):
        # 查找未同步的决策
        unsync_trades = self._find_unsync_trades()
        
        for trade in unsync_trades:
            try:
                self._sync_to_agent_os(trade)
            except Exception as e:
                logger.error(f"Compensation failed: {e}")
```

---

## 七、部署与运维

### 7.1 服务启动顺序

```bash
# 1. 启动 PostgreSQL
brew services start postgresql@14

# 2. 启动 quantsys-v2 (FastAPI)
cd quantsys-v2
source activate-py313.sh
python -m uvicorn adapters.inbound.fastapi_app.main:app \
  --host 127.0.0.1 --port 5001 --reload

# 3. 启动 agent-os (Go)
cd agent-os
./agent-os

# 4. 启动 agent-ts (TypeScript)
cd agent-ts
npm run dev
```

### 7.2 健康检查

```bash
# quantsys-v2
curl http://127.0.0.1:5001/health
# {"status": "healthy", "scheduler": "running", "orchestrator": "INTRADAY"}

# agent-os
curl http://127.0.0.1:3002/health
# {"status": "healthy", "version": "1.0.0"}

# agent-ts
curl http://127.0.0.1:3000/health
# {"status": "healthy", "session": "active"}
```

### 7.3 监控指标

```python
# 关键业务指标
metrics = {
    # 进化引擎
    'evolution': {
        'fitness_avg': 42.5,              # 平均适应度
        'decisions_scored_today': 15,     # 今日打分决策数
        'missed_opportunities': 3,        # 今日踏空数
        'top_account_fitness': 78.3,      # 最高适应度
    },
    
    # 自主能力
    'autonomy': {
        'orchestrator_phase': 'REVIEW',   # 当前阶段
        'scheduled_tasks_success_rate': 0.98,  # 任务成功率
        'watch_rules_triggered': 5,       # 今日盯盘触发数
        'agent_notifications_sent': 12,   # Agent通知数
    },
    
    # 系统健康
    'system': {
        'api_response_time_ms': 85,       # API响应时间
        'db_connections': 12,              # 数据库连接数
        'error_rate': 0.002,               # 错误率
    }
}
```

---

## 八、未来扩展点

### 8.1 文本参数进化（P0b）
- 提示词版本管理
- A/B测试框架
- 自动提示词优化

### 8.2 多Agent协作
- 决策Agent + 风控Agent + 复盘Agent
- 工作流编排
- 共识机制

### 8.3 强化学习集成
- 从适应度到RL奖励函数
- 策略梯度优化
- 离线RL训练

### 8.4 实盘交易对接
- 券商API集成
- 真实订单管理
- 滑点和手续费模拟

---

## 附录：参考文档

- [quantsys-v2 CLAUDE.md](../../quantsys-v2/CLAUDE.md)
- [agent-os README](../../agent-os/README.md)
- [agent-ts CLAUDE.md](../../agent-ts/CLAUDE.md)
- [Evolution Fitness Service](../../quantsys-v2/application/services/evolution/evolution_fitness_service.py)
- [Decision Score Service](../../quantsys-v2/application/services/evolution/decision_score_service.py)
- [Daily Orchestrator](../../quantsys-v2/application/services/daily_orchestrator.py)

---

**文档版本**: 1.0  
**最后更新**: 2026-09-03  
**作者**: PI Investment Team  
**维护**: Claude Code
