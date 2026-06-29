# Agent自动交易闭环 - 完整设计规范

日期: 2026-06-26
状态: 已批准，准备实施

---

## 1. 概述

### 1.1 目标

创建Agent自动交易闭环，让Agent操作虚拟仓证明它能通过智能决策赚钱。

### 1.2 范围

**包含：**
- 3个新增交易工具
- 2个增强的Agent任务
- 绩效追踪系统
- 完整的交易闭环

**不包含：**
- 实盘交易（仅虚拟仓）
- 外部数据源集成
- Web UI界面

---

## 2. 架构设计

### 2.1 系统架构

```
Agent-ts (AI决策层)
    ├─ 早盘分析任务
    │   ├─ 检查持仓
    │   ├─ 评估卖出
    │   ├─ 寻找买入
    │   └─ 执行交易
    ├─ 每日复盘任务
    │   ├─ 查看绩效
    │   ├─ 分析成败
    │   └─ 学习优化
    └─ 交易工具
        ├─ portfolio_trade
        ├─ portfolio_status
        └─ portfolio_analyze
            ↓ HTTP API
quantsys-v2 (交易执行层)
    ├─ /api/portfolio
    ├─ /api/portfolio/trade
    └─ SimulationTrader
        ├─ 虚拟仓管理
        ├─ T+1规则
        └─ 盈亏计算
```

### 2.2 数据流

```
Agent决策 → API调用 → 虚拟仓执行 → 数据库记录
    ↓                                      ↓
决策日志 ←────────── 绩效反馈 ←──────────┘
```

---

## 3. 详细设计

### 3.1 工具设计

#### 工具1: portfolio_trade

**输入：**
```typescript
{
  action: 'buy' | 'sell',
  symbol: string,
  reason: string,         // 必填，至少10字
  amount?: number,        // 金额（元）
  shares?: number,        // 股数
  price_limit?: number,   // 限价
  strategy?: string       // 策略名称
}
```

**输出：**
```typescript
{
  success: boolean,
  order_id?: string,
  message: string,
  details?: {
    symbol: string,
    action: string,
    price: number,
    shares: number
  }
}
```

**验证规则：**
- reason必填且>=10字
- buy时必须有可用资金
- sell时必须有持仓且T+1可卖

#### 工具2: portfolio_status

**输入：**
```typescript
{
  detailed?: boolean  // 默认false
}
```

**输出：**
```typescript
{
  cash: number,
  holdings: Array<{
    symbol: string,
    shares: number,
    cost: number,
    current_price: number,
    pnl: number,
    pnl_pct: number,
    days_held: number
  }>,
  total_value: number,
  total_pnl: number,
  total_pnl_pct: number
}
```

#### 工具3: portfolio_analyze

**输入：**
```typescript
{
  check_risk?: boolean  // 默认true
}
```

**输出：**
```typescript
{
  total_pnl: number,
  holdings_count: number,
  analysis: Array<{
    symbol: string,
    current_pnl: number,
    days_held: number,
    action: 'hold' | 'take_profit' | 'stop_loss' | 'wait_t1',
    reason: string
  }>,
  summary: string
}
```

### 3.2 任务设计

#### 任务1: morning_ai_analysis (增强版)

**执行流程：**
1. 调用portfolio_status检查持仓
2. 如有持仓，调用portfolio_analyze评估
3. 如需卖出，调用portfolio_trade执行
4. 调用market_analyze分析市场
5. 寻找买入机会（策略扫描）
6. 如有高分信号，调用portfolio_trade买入
7. 记录决策过程

**风控规则：**
- 单只≤30%
- 最多3只
- 总仓位≤80%

#### 任务2: daily_ai_review (增强版)

**执行流程：**
1. 调用portfolio_status查看绩效
2. 调用trade_monitor查看今日交易
3. 分析成功/失败案例
4. 计算绩效指标
5. 使用knowledge_record保存学习
6. 制定明日改进计划

### 3.3 API端点（quantsys-v2）

需要确认的API：
- GET /api/portfolio - 获取持仓
- POST /api/portfolio/trade - 执行交易
- GET /api/portfolio/history - 历史记录

---

## 4. 实施计划

### Phase 1: 工具开发（2-3小时）

**文件：**
- `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts`
- `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts`
- `agent-ts/src/infrastructure/tools/portfolio/portfolio-analyze-tool.ts`

**任务：**
1. 实现3个工具
2. 添加类型定义
3. 添加错误处理
4. 注册到工具系统

### Phase 2: 任务增强（1-2小时）

**文件：**
- `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts`

**任务：**
1. 修改morning_ai_analysis任务消息
2. 修改daily_ai_review任务消息
3. 添加交易相关指令

### Phase 3: 测试验证（1小时）

**任务：**
1. 手动触发Agent测试
2. 验证工具调用
3. 检查虚拟仓记录
4. 确认T+1规则

### Phase 4: 监控运行（持续）

**任务：**
1. 明天18:00验证复盘任务
2. 下周一09:00验证交易任务
3. 每日查看绩效
4. 每周生成报告

---

## 5. 验证标准

### 5.1 功能验证

- [ ] portfolio_trade工具能执行买入
- [ ] portfolio_trade工具能执行卖出
- [ ] portfolio_status工具返回正确数据
- [ ] portfolio_analyze工具给出合理建议
- [ ] Agent任务能自主调用工具
- [ ] 虚拟仓正确记录交易
- [ ] T+1规则正确执行

### 5.2 绩效验证

**1周后：**
- [ ] 至少有5笔交易
- [ ] 收益率 ≥ -5%（允许小亏学习）
- [ ] 所有交易都有理由

**1月后：**
- [ ] 收益率 > 0%
- [ ] 胜率 > 45%
- [ ] 无重大风控违规

---

## 6. 风险控制

### 6.1 交易限制

- 单只股票最大仓位: 30%
- 最大持仓数量: 3只
- 最大总仓位: 80%
- 单笔最大金额: ¥50,000

### 6.2 强制止损

- 单只亏损>8%: 强制卖出
- 总账户回撤>15%: 停止交易

### 6.3 异常处理

- API调用失败: 重试3次
- 数据异常: 跳过本次交易
- 网络超时: 记录日志，继续

---

## 7. 成功指标

### 7.1 短期（1周）

- Agent能自主交易 ✅
- 交易有明确理由 ✅
- 系统稳定运行 ✅

### 7.2 中期（1月）

- 累计收益率 > 0%
- 胜率 > 50%
- 最大回撤 < 10%

### 7.3 长期（3月）

- 累计收益率 > 10%
- 胜率 > 60%
- 夏普比率 > 1.5
- 跑赢沪深300

---

## 8. 附录

### 8.1 关键决策

**Q: 为什么必须填写交易理由？**
A: 确保Agent有明确的决策逻辑，便于后续分析和学习。

**Q: 为什么限制最多3只股票？**
A: 虚拟仓资金有限，分散太多会降低单只盈利空间，集中3只便于管理。

**Q: 如何处理T+1限制？**
A: portfolio_analyze会检查days_held，当日买入的标记为wait_t1，不会建议卖出。

### 8.2 待优化项

- [ ] 增加止盈止损自动触发
- [ ] 增加仓位管理策略
- [ ] 增加风险预警机制
- [ ] 增加绩效可视化

---

**设计完成时间:** 2026-06-26 20:00
**设计状态:** 已批准，准备实施
**预计实施时间:** 4-6小时
