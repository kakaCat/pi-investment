# 策略研发循环闭合计划

**创建时间**: 2026-05-28  
**状态**: 规划阶段  
**预估总工时**: ~42.5h（P0-1/P1/P2: ~15.5h, P3: ~8h, P4: ~19h）

---

## 📋 总体诊断

当前策略研发链路存在**三个断裂点**，导致"创建策略 → 验证策略 → 优化策略 → 部署策略"无法形成闭环：

| 断裂点 | 具体表现 | 严重度 |
|--------|---------|--------|
| 参数搜索缺失 | `strategy.optimize` 是假优化器，不用真实回测打分 | P0 🔴 |
| 策略类型有限 | Agent 只能调用 4/18 种内置策略，用户只能创建 2 种模板 | P1 🟡 |
| 知识无法积累 | 信号发了就忘，不知道哪个策略真的赚钱，经验库是空的 | P2 🟡 |
| 缺少风控熔断 | 策略连续亏损不降级，无市场风格感知，无版本管理 | P3 🔵 |
| 回测≠实盘 | 零滑点零手续费，无组合管理，Agent 无法自主创造策略 | P4 ⚪ |

---

## P0-1：参数搜索 — 真实优化引擎

### 现状

`strategy.optimize` 命令**回退到 v1 的假优化器**（`quant/quantsys/cli/strategy_optimizer.py`）：

- **不做真实回测**，只用固定公式打分：`base = 100 - abs(entry_rsi - 30) * 1.8 - abs(exit_rsi - 70) * 1.2`
- 打分逻辑不涉及任何市场数据，纯粹是"参数离预设值越近分越高"
- 只支持 3 种硬编码策略（rsi / ma_cross / bollinger）
- quantsys-v2 中**零优化基础设施**

### 目标

把假优化器替换成真实参数搜索引擎，每组参数 → 跑完整回测 → 用真实指标打分。

### 技术设计

```
参数网格定义
    │
    ▼
┌─────────────────────────────────┐
│ StrategyOptimizer (新)          │
│                                 │
│  param_grid: {                  │
│    fast: [5, 10, 20],           │
│    slow: [20, 50, 60]           │
│  }                              │
│         │                       │
│         ▼                       │
│  ┌──────────────────────┐       │
│  │ 并行回测执行器        │       │
│  │ concurrent.futures    │       │
│  │ ThreadPoolExecutor    │       │
│  │                      │       │
│  │  (fast=5, slow=20) → │       │
│  │  (fast=5, slow=50) → │       │
│  │  (fast=10, slow=20) →│  ...  │
│  └──────┬───────────────┘       │
│         │                       │
│         ▼                       │
│  按 Sharpe/收益/胜率排序         │
│  输出 Top N + 参数曲面数据      │
└─────────────────────────────────┘
    │
    ▼
 POST /api/strategies/optimize
    │
    ▼
 Agent: quant_cli strategy.optimize
```

### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `SearchSpace` 数据模型 + 参数网格生成器 | 1h |
| 2 | `StrategyOptimizer` — 并行回测执行引擎（复用 `StrategyCodeService.backtest`） | 1.5h |
| 3 | `POST /api/strategies/optimize` API 端点 | 0.5h |
| 4 | `strategy.optimize` CLI 命令重写（指向 v2，替代 v1 假优化器） | 0.5h |
| 5 | 端到端测试 + Agent 工具对接 | 1h |
| **合计** | | **~4.5h** |

### 与其他模块关系

| 依赖 | 状态 |
|------|------|
| `StrategyCodeService.backtest()` | ✅ 已存在 |
| `StrategyFactory` | ✅ 已存在 |
| `concurrent.futures` | ✅ Python 标准库 |
| P0-2（performance DB） | 不需要（后续改进可加） |

---

## P1：策略类型扩展 — Agent 可见 + 用户模板

### 现状

系统实际有 **18 种**内置策略（通过 `StrategyFactory.auto_discover` 注册），但 Agent 只能接触到 **4 种**：

```
StrategyFactory 自动发现（18 种）         Agent 可见（4 种）
─────────────────────────────────        ─────────────────
ma_cross              ✅ 均线交叉        
rsi_reversal          ✅ RSI 反转        VolatilityBreakout
bollinger_breakout    ✅ 布林带突破       Turtle
turtle_strategy       ✅ 海龟            DonchianChannel
donchian_channel      ✅ 唐奇安通道       Momentum
momentum_strategy     ✅ 动量
breakout_strategy     ✅ 突破            ❌ 其余 14 种不可见
mean_reversion        ✅ 均值回归
volatility_breakout   ✅ 波动率突破
pairs_correlation     ✅ 配对交易
multi_factor          ✅ 多因子
ml_prediction         ✅ ML 预测
adx_trend             ✅ ADX 趋势
cci_reversal          ✅ CCI 反转
grid_trading          ✅ 网格交易
config_driven         ✅ 配置驱动
multi_factor_swing    ✅ 多因子波段
ensemble_vote         ✅ 集成投票
```

此外，用户自定义策略只支持 `indicator` / `script` 两种模板，无法直接基于成熟策略范式创建。

### 目标

1. Agent 的 `strategy_execute` 工具动态支持全部 18 种策略
2. 新增 3 种用户模板：趋势跟踪、均值回归、多因子

### 技术设计

```
A. Agent 工具层 — 动态注册

strategy_execute(symbol, strategy) {
  strategies = GET /api/strategies/list  ← 动态获取
  strategy_type = strategies.find(s => s.matches(strategy))
  executor = StrategyFactory.create(strategy_type)
  return executor.run(symbol)
}

B. 用户模板扩展

code_type: 'indicator' | 'script' | 'trend_following' | 'mean_reversion' | 'multi_factor'
                                         ↑ 新增                ↑ 新增          ↑ 新增

trend_following 模板：
  - 继承自 ma_cross / turtle / donchian / adx_trend
  - 提供: 快慢均线、通道宽度、ATR 倍数等参数

mean_reversion 模板：
  - 继承自 rsi_reversal / cci_reversal / bollinger_breakout
  - 提供: 超买/超卖阈值、回归周期、布林带宽等参数

multi_factor 模板：
  - 继承自 multi_factor_strategy / multi_factor_swing
  - 提供: 因子列表、权重配置、打分阈值等参数
```

### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `strategy_execute` 从硬编码 4 种 → 动态读取 `StrategyFactory.list_all()` | 0.5h |
| 2 | 新增 `GET /api/strategies/list` API，返回 18 种策略元数据 | 0.5h |
| 3 | 3 种新用户模板的代码模板 + 校验器 | 2h |
| 4 | `StrategyCodeService.create` 支持 `code_type` 扩展到 5 种 | 1h |
| 5 | Agent 工具文档更新 + `quant_cli help` 同步 | 0.5h |
| **合计** | | **~4.5h** |

### 与其他模块关系

| 依赖 | 状态 |
|------|------|
| `StrategyFactory` (18 种策略) | ✅ 已存在 |
| `StrategyCodeService` | ✅ 已存在 |
| `StrategyStockMatcher`（策略-标的匹配） | ✅ 已存在 |
| P0-1（参数搜索） | 不需要（独立推进） |

---

## P2：知识积累 + 实盘跟踪（统一闭环）

### 现状

系统已有两个相关基础设施，但**各自孤立运行，互不反馈**：

```
当前架构（两条平行线，永不交汇）：

SignalTestLog:          信号 → pending → 纸面验证 → verified → 统计（没人看）
signal_execution:       信号 → 风控检查 → 创建订单 → 结束（盈亏不追踪）
```

**SignalTestLog**（`quantsys-v2/services/signal_test_log.py`）：
- ✅ 信号写入 `quant.signal_test_log` 表
- ✅ 回扫验证：T+5 日后自动计算模拟盈亏
- ✅ 统计：胜率、平均盈亏、按月分布、按策略分布
- ❌ 统计结果不反馈到策略选择
- ❌ 不与 Agent 的 `query_experience` 工具联动

**signal_execution**（`src/infrastructure/tools/execution/signal-execution-tool.ts`）：
- ✅ 信号 → 风控 → 创建订单
- ✅ 执行日志、统计
- ❌ 订单创建后**不追踪盈亏**
- ❌ 不标记订单来源信号（无法关联）

### 目标

把两条线接起来，形成"信号 → 执行 → 结算 → 反馈 → 优化下次信号"的完整闭环。

### 技术设计

```
P2 闭环：

策略信号 ──→ [风控] ──→ 创建订单 ──→ 成交
    ↑                                    ↓
    │                              追踪持仓盈亏
    │                                    ↓
    │                              T+N 结算盈亏
    │                                    ↓
    └──── 反馈：更新策略权重 ──── strategy_performance DB
```

**A. 策略表现数据库** — `quant.strategy_performance` 表

| 字段 | 说明 |
|------|------|
| `strategy_name` | 策略名称 |
| `symbol` | 标的 |
| `signal_date` | 信号产生日期 |
| `entry_price` | 入场价 |
| `exit_price` | 出场价 |
| `pnl_pct` | 盈亏百分比 |
| `holding_days` | 持仓天数 |
| `scenario_tags` | 场景标签（如 `rsi_oversold`, `bull_market`） |
| `params_snapshot` | 参数快照（JSON） |
| `source` | `paper`（纸面测试）/ `live`（实盘） |

**B. 信号 → 订单 → 盈亏追踪**

```
signal_execution 创建订单时:
  → trade_manage_orders.place() 创建订单
  → signal_test_log 写入同一条记录，标记 source='live', order_id='xxx'

trade_manage_orders.fill() 成交时:
  → 更新 portfolio
  → 回写 signal_test_log: entry_price = fill_price

用户卖出/减仓时:
  → portfolio_rebalance.sell()
  → 回写 signal_test_log: exit_price, pnl_pct
  → 同步写入 strategy_performance

经验自动积累:
  → SignalTestLog.get_stats() 每周自动汇总
  → 写入 query_experience 可查询的经验条目
  → Agent 做决策时返回：'该策略在类似条件下胜率 68%，平均收益 +3.2%'
```

**C. 经验库自动更新**

```
每周定时任务:
  1. SignalTestLog.verify_pending(days_after=5)
  2. 汇总 verified 信号的 statistics
  3. 有条件地写入 experience 条目:
     - 样本 ≥ 10: 写入策略级经验
     - 样本 ≥ 30: 写入策略+场景级经验
     - 样本 ≥ 50: 写入策略+场景+标的级经验
```

### 计划

| # | 内容 | 依赖 | 估时 |
|---|------|------|------|
| 1 | `quant.strategy_performance` 表 + `StrategyPerformanceDB` service | 无 | 1.5h |
| 2 | 订单→盈亏追踪：`fill`/`sell` 时回写 `signal_test_log` + `strategy_performance` | 无 | 1.5h |
| 3 | 纸面+实盘统一统计 API：`GET /api/signal-test/performance` | 步骤1 | 1h |
| 4 | 经验自动积累：统计结果 → `query_experience` 可查询条目 | 步骤3 | 1.5h |
| 5 | Agent 工具文档更新 + 端到端验证 | 全部 | 1h |
| **合计** | | | **~6.5h** |

### 与其他模块关系

| 依赖 | 状态 |
|------|------|
| `SignalTestLog` | ✅ 已存在 |
| `signal_execution` 工具 | ✅ 已存在 |
| `trade_manage_orders` 工具 | ✅ 已存在 |
| `portfolio_rebalance` 工具 | ✅ 已存在 |
| `query_experience` 工具 | ✅ 已存在 |
| P0-2（performance DB 表） | 与步骤1 重叠，可合并 |
| P0-1（参数搜索） | 不依赖 |
| P1（策略类型扩展） | 不依赖 |

---

## 📅 执行策略

### 依赖关系图

```
P0-1 (参数搜索)  ──→ 无依赖，可立即开始
P1 (策略类型扩展) ──→ 无依赖，可立即开始
                    ↓
P2 (知识+实盘) ────→ 最好等 P0-2（performance DB 表）就绪后开始
                    （但步骤1 就建了 performance DB 表，所以可以独立推进）
P3 (策略运维) ────→ 三个子项互不依赖，随时可启动
                    （P3-2 依赖 factor_calculate，已就绪）
P4 (能力升级) ────→ 推荐 A → D → B → C
                    P4-A 无依赖，其他依赖 P0-1/P3 部分成果
```

### 推荐执行顺序

```
批次1（并行）:   P0-1 + P1            (~9h，2 人并行 ~4.5h)
批次2:           P2 步骤1-2           (~3h)
批次3:           P2 步骤3-5 + P4-A    (~7.5h，P4-A 现在做让后续回测都准)
批次4（并行）:   P3-1 + P3-2 + P3-3   (~8h)
批次5:           P4-D                (~4h)
批次6:           P4-B                (~5h)
批次7:           P4-C                (~6h)
──────────────────────────────────────────
预期总日历时间:  ~42h（串行）/ ~20h（关键批次并行）
```

### 各批次完成的验证标准

**P0-1 完成标志**：
- `POST /api/strategies/optimize` 返回真实回测评分的最优参数
- `quant_cli strategy.optimize` 不再使用 v1 假优化器
- 100 组参数搜索在 60s 内完成

**P1 完成标志**：
- `strategy_execute` 可调用全部 18 种策略
- 用户可通过 `code_type: 'trend_following'` 创建策略
- Agent 分析时自动匹配可用策略类型

**P2 完成标志**：
- 一笔信号从生成 → 订单 → 成交 → 盈亏结算，全程可追踪
- `query_experience` 返回的数据来自真实信号验证（非静态规则）
- `GET /api/signal-test/performance` 统一展示纸面+实盘绩效

---

## P3：策略运维与自适应 — 闭环运转后的质量优化

**定位**: P0-1/P1/P2 解决"闭环断裂"问题后，P3 确保闭环运转的质量和韧性。三个子项可独立推进。

### P3-1：策略熔断

#### 现状

无熔断机制。某策略连续发出错误信号时，系统不会降级或告警，Agent 可能继续调用并产生亏损。

#### 目标

策略连续失败 → 自动降级为 paper-only → Agent 只能纸面观察 → 恢复后再重新开放实盘。

#### 技术设计

```
策略熔断状态机：

                   ┌──────────┐
          ┌───────→│  ACTIVE  │←───────┐
          │        └────┬─────┘        │
          │    连续损    │  连续N次     │
          │    失 < N   │  亏损 ≥ N    │
          │             ▼              │
          │   ┌──────────────┐         │
          │   │  WARNING     │     恢复条件:
          │   │  实盘+告警   │     连续 M 次
          └───┤  (可手动降级)│     信号盈利
              └──────┬───────┘         │
               超过  │  超过            │
              阈值%  │  阈值%           │
                     ▼                  │
              ┌──────────────┐         │
              │  SUSPENDED   │─────────┘
              │  仅 paper    │
              │  Agent 收到  │
              │  'avoid' 建议│
              └──────────────┘
```

**核心指标**：
- `consecutive_losses` — 连续亏损次数
- `rolling_win_rate` — 滚动 20 笔信号胜率
- `max_drawdown` — 信号序列最大回撤

#### 触发条件（可配）

| 条件 | 默认值 | 动作 |
|------|--------|------|
| 连续亏损 ≥ 5 次 | — | → WARNING |
| 滚动胜率 < 30%（20笔） | — | → WARNING |
| 累计回撤 ≥ 20% | — | → SUSPENDED |
| WARNING 后连亏 ≥ 8 次 | — | → SUSPENDED |
| SUSPENDED 后连盈 ≥ 3 次 | — | → ACTIVE（需人工确认） |

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `StrategyCircuitBreaker` service — 熔断状态机 + DB 存储 | 1h |
| 2 | `signal_execution` 集成：执行前检查熔断状态，Active 才允许实盘 | 0.5h |
| 3 | 告警通知：SUSPENDED 时自动发 `risk_warning` 到 Feishu | 0.5h |
| **合计** | | **~2h** |

---

### P3-2：市场风格检测

#### 现状

无市场风格感知。趋势策略在震荡市和震荡策略在趋势市表现都差，但没有机制让系统自动调整。

#### 目标

用因子收益截面识别市场风格 → 按风格调整策略权重 → Agent 推荐策略时考虑当前风格。

#### 技术设计

```
市场风格检测流程:

每日收盘后:
  ↓
1. 计算因子日收益截面（Fama-French / Barra 风格因子）
   - 动量因子收益 → ↑ = 动量市
   - 价值因子收益 → ↑ = 价值市
   - 规模因子收益 → ↑ = 小盘风格
   - 波动率因子收益 → ↑ = 低波风格
  ↓
2. 判断主导风格: 过去 20 日因子收益均值最大的方向
  ↓
3. 调整策略权重:
   ┌───────────────┬──────────┬──────────┬──────────┬──────────┐
   │ 策略类型       │ 动量市    │ 价值市    │ 震荡/低波  │ 小盘风格  │
   ├───────────────┼──────────┼──────────┼──────────┼──────────┤
   │ 趋势跟踪       │ +30%     │ -10%     │ -40%     │ NC       │
   │ 均值回归       │ -20%     │ NC       │ +30%     │ NC       │
   │ 多因子         │ +10%     │ +20%     │ NC       │ +15%     │
   │ 配对交易       │ NC       │ NC       │ NC       │ NC       │
   └───────────────┴──────────┴──────────┴──────────┴──────────┘
  ↓
4. Agent 的 strategy_execute 输出附加字段:
   `recommendation_override: "当前为动量市，趋势策略加成30%"`
```

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `MarketStyleDetector` — 因子日收益计算 + 风格归因 | 1.5h |
| 2 | 策略权重调整器：读风格 → 输出加权矩阵 | 1h |
| 3 | Agent `strategy_execute` 集成风格建议字段 | 0.5h |
| **合计** | | **~3h** |

---

### P3-3：策略版本管理

#### 现状

`StrategyCodeService.update()` 直接覆盖策略代码。用户调参后旧版本丢失，无法回滚，无法 A/B 对比。

#### 目标

每次保存策略时自动创建版本快照 → 支持版本列表、diff 对比、回滚、A/B 测试。

#### 技术设计

```
quant.strategy_codes 增加版本支持:

策略 code_id = "my_ma_strategy"
  ├── v1 (2026-05-20):  code → "fast=5, slow=20, ..."  ✅ 当前生效
  ├── v2 (2026-05-25):  code → "fast=10, slow=30, ..."  (回测中)
  └── v2 (2026-05-25):  code → "fast=10, slow=30, ..."

quant.strategy_versions 表:
  ├── version_id
  ├── code_id (FK)
  ├── version_number
  ├── code_content
  ├── params_snapshot (JSON)
  ├── change_description
  ├── created_at
  └── metrics: { sharpe, win_rate, ... }  ← 回测结果

API:
  POST   /api/strategies/versions?code_id=xxx&action=save     → 保存新版本
  GET    /api/strategies/versions?code_id=xxx                  → 版本列表
  GET    /api/strategies/versions/diff?v1=x&v2=y               → 版本对比
  POST   /api/strategies/versions/rollback?code_id=xxx&version=3 → 回滚
  POST   /api/strategies/versions/ab-test                      → 创建 A/B 测试
```

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `quant.strategy_versions` 表 + `StrategyVersionService` | 1h |
| 2 | `StrategyCodeService` 改造：create/update → 自动写版本 | 1h |
| 3 | API 端点：版本列表、diff、回滚 | 1h |
| **合计** | | **~3h** |

---

### P3 执行策略

```
P3-1 (策略熔断)  ──→ 无依赖，可独立开始
P3-2 (风格检测)  ──→ 依赖 factor_calculate（已就绪）
P3-3 (版本管理)  ──→ 无依赖，可独立开始
```

三个互不依赖，可以并行推进。

### P3 完成标志

**P3-1**：某策略连亏 5 次后 Agent 收到 `circuit_breaker: suspended`，不再创建实盘订单。

**P3-2**：Agent 调用 `strategy_execute` 时返回字段包含 `market_style` 和 `style_adjusted_weight`。

**P3-3**：用户修改策略参数 → 版本历史保留 → 可一键回滚到旧版本。

---

## P4：能力升级 — 从"能跑"到"跑得好"

**定位**: P0-P3 修复闭环断裂 + 建立运维机制后，P4 提升闭环内每个环节的执行质量。四个方向无强制顺序，按实际需求选做。

---

### P4-A：回测质量升级

#### 现状

回测是理想化执行模型：零滑点、零手续费、无限流动性、无涨跌停限制。这种回测结果搬到实盘中，必然出现显著偏差（尤其是小盘股和高波动标的）。

#### 问题拆解

| 现实摩擦 | 当前回测 | 影响 |
|---------|---------|------|
| **交易成本** | 无手续费 | 高频/短线策略虚增收益 0.5-2%/年 |
| **滑点** | 零滑点 | 小盘股实盘滑点可达 0.3-0.8% |
| **市场冲击** | 无限流动性 | 大单量策略在回测中不会推高买入价 |
| **涨跌停** | 信号日可成交 | A股涨跌停无法买入/卖出，信号虚增 |

#### 目标

回测结果 ±5% 以内逼近实盘（当前偏差通常 >10%，小盘股 >20%）。

#### 技术设计

```
回测成本模型（三个维度叠加）:

1. 手续费层
   ├── A股: 佣金万2.5 + 印花税千1(卖) + 过户费万0.2
   ├── 港股: 佣金万5 + 印花税千1.3(买卖) + 交易征费 + 交收费
   └── 可配置: 自定义费率

2. 滑点层
   ├── 固定滑点: 涨/跌各 N tick（保守默认 1bp）
   ├── 波动率滑点: sigma = atr/close * spread_factor
   │   → 波动越大，滑点越大
   └── 成交量加权: 成交量越小，滑点越大
       slip = base_slip * (1 + vol_ratio_factor / sqrt(volume_percentile))

3. 流动性层
   ├── 最大可成交量 = min(order_qty, 当日成交量 * max_participation%)
   │   → 单笔不超过日成交量 5%
   ├── 冲击成本 = sqrt(order_qty / daily_volume) * impact_coefficient
   │   → 大单量额外加冲击成本
   └── 涨跌停检查: 涨停→无法买入, 跌停→无法卖出
```

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `TransactionCostModel` — 手续费+印花税多市场计算 | 1h |
| 2 | `SlippageModel` — 三层滑点叠加 | 1.5h |
| 3 | `LiquidityModel` — 成交量约束+冲击成本+涨跌停过滤 | 1h |
| 4 | 集成到 `StrategyCodeService.backtest` 的结算环节 | 0.5h |
| **合计** | | **~4h** |

---

### P4-B：策略组合管理

#### 现状

用户同时有多条策略在跑时，问题无解：
- 策略 A 说买，策略 B 说卖 → 信谁？
- 两个策略同时推同一只标的 → 仓位怎么分？
- 整体持仓已经偏重某个行业，新信号还要不要跟？

#### 目标

从"单策略信号"提升到"组合级决策"，平衡多策略冲突 + 行业/风险分散。

#### 技术设计

```
策略组合管理三层架构:

┌─────────────────────────────────────────────┐
│ 1. 信号层 — 信号收集与冲突裁决              │
│                                             │
│  策略A: 600519 BUY  置信度=0.72              │
│  策略B: 600519 SELL 置信度=0.55              │
│  策略C: 000858 BUY  置信度=0.68              │
│         ↓                                   │
│  SignalArbiter(已存在) 裁决:                 │
│  600519 → BUY (A 置信度 > B)                 │
│  ← 当前 SignalArbiter 只做这个，不够          │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 2. 组合层 — 资金分配 + 风险预算              │
│                                             │
│  可配仓位 = 总资金 * 风险预算%               │
│  策略间相关矩阵（历史信号重叠度）:            │
│      A    B    C                            │
│  A   1.0  0.3  0.7                          │
│  B   0.3  1.0  0.2                          │
│  C   0.7  0.2  1.0                          │
│         ↓                                   │
│  A和C高度相关 → 共享风险预算                 │
│  单标的仓位 = Kelly / (1 + 相关策略数)       │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 3. 约束层 — 组合级别硬约束                   │
│                                             │
│  ✔ 单票 ≤ 总资金 20%                        │
│  ✔ 单行业 ≤ 总资金 40%                      │
│  ✔ 总仓位 ≤ 80%（永不满仓）                  │
│  ✔ 相关策略组 ≤ 50%                         │
│  ✔ 现金预留 ≥ 20%                           │
└─────────────────────────────────────────────┘
```

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `PortfolioRiskBudget` — 风险预算计算 + 策略相关性矩阵 | 1.5h |
| 2 | `PortfolioConstraintEngine` — 组合级硬约束检查 | 1.5h |
| 3 | `POST /api/signals/arbitrate` 扩展：裁决 + 仓位分配 + 约束检查 | 1.5h |
| 4 | Agent `signal_execution` 集成组合级决策输出 | 0.5h |
| **合计** | | **~5h** |

---

### P4-C：Agent 自主研发策略

#### 现状

Agent 只能**调用**已有策略，不能**创造**策略。用户想试一个新思路时，必须手工写策略代码 → 回测 → 再让 Agent 分析结果。中间全靠人肉衔接。

#### 目标

Agent 驱动 P0-1 的优化引擎，完成"提出问题 → 搜索参数 → 回测验证 → 决定上线"的全自动研发流程。

#### 技术设计

```
Agent 自主策略研发流程:

用户: "帮我找一个适合当前市场的中短线策略"

Agent:
  ↓
1. 分析当前市场状态
   → P3-2 的市场风格检测: "当前震荡偏弱，波动率低位"
   → 适合策略类型: 均值回归 > 网格 > 多因子
   → 不适合: 趋势跟踪（无趋势可跟）
  ↓
2. 生成策略搜索空间
   选择均值回归模板，定义搜索空间:
   {
     lookback: [10, 20, 30],
     oversold_threshold: [20, 25, 30],
     exit_rsi: [50, 55, 60],
     stop_loss_pct: [0.03, 0.05, 0.08]
   }
  ↓
3. 调用 P0-1 参数搜索
   → POST /api/strategies/optimize (360 组参数, ~2分钟)
   → Top 5 按 Sharpe 排序
  ↓
4. 对 Top 5 做样本外验证
   → 用最近 60 天数据（不在搜索训练期内）
   → 筛选样本外表现稳定的参数
  ↓
5. 生成策略代码
   → StrategyCodeService.create(code_type='mean_reversion', params=best)
   → 自动写入 quant.strategy_versions
  ↓
6. 决策建议
   "均值回归策略，参数 lookback=20, oversold=25, exit_rsi=55
    回测 Sharpe 1.8，样本外 Sharpe 1.5，建议纸面观察5天后上线"
```

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `StrategyDiscoverService` — 市场状态→策略类型匹配器 | 1h |
| 2 | `AutoStrategyPipeline` — 串联: 选型→搜索→验证→生成代码 | 2h |
| 3 | `POST /api/strategies/auto-discover` API | 1h |
| 4 | Agent 工具: `strategy_discover` — 接收自然语言需求 → 触发全管线 | 1.5h |
| 5 | 端到端测试流程 | 0.5h |
| **合计** | | **~6h** |

---

### P4-D：实盘质量监控

#### 现状

策略上线后没有系统化的质量监控：
- 不知道回测预期收益和实盘实际收益的偏差
- 滑点、未成交、延迟等问题发现不了
- 出了问题只能靠手动复盘

#### 目标

实盘运行时自动采集质量指标 → 偏差超阈值自动告警 → Agent 做决策时感知实盘偏差。

#### 技术设计

```
实盘质量监控面板（4 个维度实时对比）:

┌──────────────────────────────────────────────────────┐
│ 1. 收益偏离度                                        │
│                                                      │
│  策略入池时回测            实盘运行中                  │
│  ┌─────────────────┐     ┌─────────────────┐         │
│  │ Sharpe:    1.85  │     │ Sharpe:    0.92  │ ← 偏离  │
│  │ 胜率:      62%   │     │ 胜率:      48%  │         │
│  │ 最大回撤: -12%   │     │ 最大回撤: -18%  │         │
│  │ 日均收益: +0.15% │     │ 日均收益: +0.03%│         │
│  └─────────────────┘     └─────────────────┘         │
│                                                      │
│  偏离度 = (实盘Sharpe - 回测Sharpe) / 回测Sharpe      │
│  → 严重偏离 (< -50%) → ⚠️ 策略可能过拟合或失效       │
├──────────────────────────────────────────────────────┤
│ 2. 执行质量                                          │
│                                                      │
│  ┌──────────────┬────────┬────────┐                  │
│  │ 指标          │ 预期    │ 实际    │                  │
│  ├──────────────┼────────┼────────┤                  │
│  │ 平均滑点      │ 0.10%  │ 0.35%  │ ← 超标          │
│  │ 成交率        │ 100%   │ 87%    │ ← 异常          │
│  │ 信号→订单延迟 │ <5s    │ 3.2s   │ ✅              │
│  │ 数据延迟      │ <2s    │ 1.8s   │ ✅              │
│  └──────────────┴────────┴────────┘                  │
├──────────────────────────────────────────────────────┤
│ 3. 标的约束检查                                      │
│                                                      │
│  信号标的在小盘/高价/低流动性池中？                    │
│  → 自动标记高风险标的，降权处理                       │
├──────────────────────────────────────────────────────┤
│ 4. 异常检测                                          │
│                                                      │
│  自动检测模式异常:                                    │
│  ├── 信号频率突变（突然增多/减少）                    │
│  ├── 交易时间异常（集中开盘/尾盘）                    │
│  ├── 标的集中度异常（过度集中于某行业）               │
│  └── 数据源中断（kline/hq 更新时间戳不更新）          │
└──────────────────────────────────────────────────────┘
```

#### 告警规则

| 条件 | 级别 | 动作 |
|------|------|------|
| 收益偏离度 > 50% | 🔴 high | 自动 SUSPEND + Feishu + Agent 收到 risk_warning |
| 滑点超标 2x | 🟡 medium | 调整滑点模型参数，提示用户 |
| 成交率 < 80% | 🔴 high | 检查流动性模型，可能标的不适合该策略 |
| 数据源中断 > 5min | 🔴 high | 暂停所有新信号生成 |
| 标的集中度 > 60% | 🟡 medium | 提示行业风险 |

#### 计划

| # | 内容 | 估时 |
|---|------|------|
| 1 | `LiveQualityCollector` — 每笔成交时自动采集执行指标 | 1.5h |
| 2 | `LiveVsBacktestComparator` — 回测vs实盘偏离度计算 | 1h |
| 3 | `AnomalyDetector` — 信号频率/交易模式/集中度异常检测 | 1h |
| 4 | Agent `monitor_alert` 集成：超阈值自动发告警 | 0.5h |
| **合计** | | **~4h** |

---

### P4 执行策略

```
P4-A (回测质量) ──→ 无依赖，建议最先做（所有回测都变准）
P4-B (组合管理) ──→ 依赖 SignalArbiter（已存在） + P4-A（准的回测）
P4-C (自主研发) ──→ 依赖 P0-1 + P3-2（风格检测）
P4-D (实盘监控) ──→ 依赖 P3-1（策略熔断，告警→降级）
```

**推荐顺序**：A → D → B → C（先让回测准、再让监控到位、再做组合级决策、最后让 Agent 自主研发）。

### P4 完成标志

**P4-A**：同一策略的回测收益与实盘收益偏差 ≤ 5%。

**P4-B**：三策略同时推信号时不冲突，仓位总和不超过资金约束。

**P4-C**：用户说"帮我找一个中短线策略" → Agent 10 分钟内返回已验证的策略代码 + 样本外回测报告。

**P4-D**：策略实盘偏离超阈值时，Agent 主动推送告警："600519 交易策略实盘 Sharpe 偏离回测 60%，建议检查"。
