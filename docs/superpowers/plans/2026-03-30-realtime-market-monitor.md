# 实时盯盘系统实现计划

**日期**: 2026-03-30
**目标**: 实现 Agent 驱动的自适应实时盯盘系统，通过飞书通知交易信号

## 核心架构

```
硬编码快速过滤（本地计算）→ Agent 深度分析（LLM）→ Agent 决定下次检查时间
                                    ↓
                            飞书通知交易信号
```

## 实现任务

### Task 1: 飞书通知服务

**文件**: `src/services/notification/feishu-service.ts`

**功能**:
- 发送交易信号卡片到飞书 webhook
- 支持买入/卖出两种信号类型
- 卡片包含：股票信息、当前价、置信度、理由、建议仓位

**接口**:
```typescript
interface TradeSignal {
  action: 'buy' | 'sell'
  symbol: string
  name: string
  price: number
  reason: string
  confidence: number
  position_pct: number
}

class FeishuService {
  async sendTradeAlert(signal: TradeSignal): Promise<void>
}
```

**环境变量**: 需要在 `.env` 中配置 `FEISHU_WEBHOOK_URL`

---

### Task 2: 市场快速过滤器

**文件**: `src/services/monitor/market-filter.ts`

**功能**:
- 硬编码规则快速判断市场状态
- 识别高波动、放量、接近关键位、突破等信号
- 计算紧急度（0-3）
- 返回是否需要 Agent 分析

**过滤规则**:
- 高波动: 涨跌幅 > 3%
- 放量: 成交量 > 均量 * 2
- 接近关键位: 距离支撑/压力位 < 2%
- 突破: 价格突破压力位

**接口**:
```typescript
interface FilterResult {
  needsAgentAnalysis: boolean
  urgency: number  // 0=平淡, 1=正常, 2=活跃, 3=紧急
  candidates: Quote[]
  signals: {
    high_volatility: Quote[]
    high_volume: Quote[]
    near_support: Quote[]
    breakout: Quote[]
  }
}

export function quickFilter(quotes: Quote[], portfolio: Portfolio): FilterResult
```

---

### Task 3: 监控工具定义

**文件**: `src/tools/monitor-tools.ts`

**新增 2 个工具**:

1. **send_feishu_alert** - 发送交易信号到飞书
   ```typescript
   {
     name: "send_feishu_alert",
     description: "发送交易信号到飞书通知用户",
     input_schema: {
       type: "object",
       properties: {
         action: { type: "string", enum: ["buy", "sell"] },
         symbol: { type: "string" },
         name: { type: "string" },
         price: { type: "number" },
         reason: { type: "string", description: "详细理由（技术面+基本面）" },
         confidence: { type: "number", minimum: 0, maximum: 1 },
         position_pct: { type: "number", description: "建议仓位百分比" }
       },
       required: ["action", "symbol", "name", "price", "reason", "confidence"]
     }
   }
   ```

2. **schedule_next_check** - Agent 决定下次检查时间
   ```typescript
   {
     name: "schedule_next_check",
     description: "根据市场状态设置下次盯盘时间",
     input_schema: {
       type: "object",
       properties: {
         minutes: {
           type: "number",
           minimum: 1,
           maximum: 60,
           description: "多少分钟后检查"
         },
         reason: {
           type: "string",
           description: "为什么选择这个时间间隔"
         }
       },
       required: ["minutes", "reason"]
     }
   }
   ```

**实现**: 调用 `FeishuService` 和 `CronService`

---

### Task 4: 监控服务核心逻辑

**文件**: `src/services/monitor/market-monitor-service.ts`

**功能**:
- 定时触发（由 CRON 或手动调用）
- 拉取实时行情
- 调用 `quickFilter` 快速过滤
- 如果需要，调用 Agent 深度分析
- Agent 自动调用 `send_feishu_alert` 和 `schedule_next_check`

**核心方法**:
```typescript
class MarketMonitorService {
  async tick(): Promise<void> {
    // 1. 获取行情
    const quotes = await this.fetchQuotes()

    // 2. 快速过滤
    const filter = quickFilter(quotes, this.portfolio)

    if (!filter.needsAgentAnalysis) {
      await this.scheduleNext(30, "市场平淡")
      return
    }

    // 3. Agent 分析
    await this.agent.run({
      systemPrompt: MONITOR_SYSTEM_PROMPT,
      userMessage: this.buildContext(filter)
    })
  }

  private async fetchQuotes(): Promise<Quote[]>
  private buildContext(filter: FilterResult): string
  private async scheduleNext(minutes: number, reason: string): Promise<void>
}
```

**Agent System Prompt**:
```
你是实时盯盘助手。

职责：
1. 分析市场和持仓，判断是否有交易信号
2. 根据市场状态决定下次检查时间

决策逻辑：
- 发现明确信号 → send_feishu_alert + schedule_next_check(30, "已发信号，等待执行")
- 接近关键位 → schedule_next_check(1, "接近支撑位，密切关注")
- 市场活跃但无信号 → schedule_next_check(5, "市场波动，保持关注")
- 市场平淡 → schedule_next_check(30, "市场平淡")

信号标准：
- 置信度 >= 0.7
- 有明确的技术面+基本面支撑
- 理由具体可执行
- 同一股票 30 分钟内不重复通知
```

---

### Task 5: 集成到主入口

**修改文件**:
- `src/tools/invest-tools.ts` - 注册新工具
- `src/api/index.ts` - 添加监控启动入口

**新增 API**:
```typescript
// 手动触发盯盘
app.post('/api/monitor/tick', async (req, res) => {
  await marketMonitorService.tick()
  res.json({ success: true })
})

// 启动自动盯盘
app.post('/api/monitor/start', async (req, res) => {
  await marketMonitorService.start()
  res.json({ success: true })
})

// 停止盯盘
app.post('/api/monitor/stop', async (req, res) => {
  await marketMonitorService.stop()
  res.json({ success: true })
})
```

---

### Task 6: CRON 配置

**文件**: `.pi-invest/CRON.json`

**新增定时任务**:
```json
{
  "schedules": [
    {
      "name": "market-monitor-start",
      "kind": "at",
      "expr": "30 9 * * 1-5",
      "prompt": "开始今日盯盘",
      "enabled": true
    },
    {
      "name": "market-monitor-stop",
      "kind": "at",
      "expr": "01 15 * * 1-5",
      "prompt": "停止盯盘，准备收盘",
      "enabled": true
    }
  ]
}
```

---

## 技术要点

1. **硬编码过滤优先** - 减少 Agent 调用成本
2. **Agent 自主决策** - 下次检查时间由 Agent 根据市场状态决定
3. **去重机制** - 同一股票 30 分钟内不重复通知
4. **交易时段限制** - 只在 9:30-15:00 运行
5. **环境变量** - 飞书 webhook URL 从 `.env` 读取

## 依赖

- 现有的 `AgentLoop` (src/core/agent/agent-loop.ts)
- 现有的 `CronService` (src/services/cron/cron-service.ts)
- 现有的 `PortfolioService` (src/services/portfolio/portfolio-service.ts)
- 现有的 AkShare-TS 数据层

## 测试验证

1. 手动触发 `/api/monitor/tick` 验证流程
2. 检查飞书是否收到通知
3. 验证 Agent 是否正确调用 `schedule_next_check`
4. 验证去重机制是否生效
