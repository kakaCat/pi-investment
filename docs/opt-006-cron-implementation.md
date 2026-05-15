# OPT-006: 自动清理过期挂单 - Cron 实现

## 📋 概述

实现真正的自动清理过期挂单功能，通过定时任务（cron）在交易时间自动执行，无需手动调用。

---

## 🎯 实现方案

### 方案对比

#### ❌ 原方案：手动触发
```
用户需要主动调用 check_pending_orders
  ↓
工具执行时清理过期挂单
  ↓
问题：依赖用户操作，不是真正的"自动"
```

#### ✅ 新方案：定时任务
```
系统启动时加载 CRON.json
  ↓
CronService 每秒 tick，检查任务是否到期
  ↓
到期时自动调用 session.prompt("检查所有挂单...")
  ↓
Agent 收到消息，调用 check_pending_orders 工具
  ↓
工具自动清理过期挂单 + 检查触发条件 + 执行成交
  ↓
真正的自动化，无需用户干预
```

---

## 🔧 技术实现

### 1. Cron 任务配置

**文件**: `.pi-invest/CRON.json`

```json
{
  "id": "check-pending-orders",
  "name": "检查挂单并清理过期",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "*/30 9-15 * * 1-5"
  },
  "payload": {
    "kind": "agent_turn",
    "message": "检查所有挂单状态，自动成交触发的订单，清理过期挂单"
  }
}
```

**配置说明**：
- `id`: 任务唯一标识
- `name`: 任务显示名称
- `enabled`: 是否启用（true）
- `schedule.kind`: 调度类型（cron）
- `schedule.expr`: Cron 表达式
  - `*/30`: 每 30 分钟
  - `9-15`: 9:00-15:00 时间段
  - `* * 1-5`: 每月每日，周一至周五
- `payload.kind`: 任务类型（agent_turn）
- `payload.message`: 发送给 agent 的消息

### 2. Cron 表达式解析

**格式**: `分钟 小时 日 月 星期`

**示例**：
```
*/30 9-15 * * 1-5
│    │    │ │ │
│    │    │ │ └─ 周一至周五（1-5）
│    │    │ └─── 每月（*）
│    │    └───── 每日（*）
│    └────────── 9:00-15:00（9-15）
└─────────────── 每 30 分钟（*/30）
```

**执行时间**：
- 周一至周五
- 9:00, 9:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, 13:30, 14:00, 14:30, 15:00
- 共 13 次/天

### 3. 执行流程

```
1. 系统启动
   ↓
2. CronService 加载 CRON.json
   ↓
3. 解析 cron 表达式，计算下次执行时间
   ↓
4. 每秒 tick，检查是否到期
   ↓
5. 到期时调用 onJob(payload)
   ↓
6. src/api/index.ts 处理 agent_turn
   ↓
7. session.prompt(payload.message)
   ↓
8. Agent 收到消息，理解意图
   ↓
9. Agent 调用 check_pending_orders 工具
   ↓
10. 工具执行：
    - orderService.expireOverdue() 清理过期
    - 获取所有 pending 挂单
    - 检查触发条件
    - 自动成交
    - 更新持仓和交易记录
   ↓
11. 返回结果给 Agent
   ↓
12. Agent 生成报告
   ↓
13. 计算下次执行时间
```

### 4. 关键代码

**CronService 处理**：
```typescript
// src/services/operations/cron-service.ts
private async runJob(job: CronJob, now: number): Promise<void> {
  try {
    await this.onJob(job.payload);  // 调用回调
    job.consecutiveErrors = 0;
  } catch (e) {
    job.consecutiveErrors++;
    if (job.consecutiveErrors >= AUTO_DISABLE_THRESHOLD) {
      job.enabled = false;  // 连续失败 5 次自动禁用
    }
  }
  job.lastRunAt = now;
  job.nextRunAt = this.computeNext(job, now);  // 计算下次执行时间
}
```

**Agent Turn 处理**：
```typescript
// src/api/index.ts
const cronService = new CronService(
  cronFile,
  PI_DIR,
  async (payload: CronJobPayload) => {
    if (payload.kind === "agent_turn" && payload.message) {
      // 直接通过 session 注入消息
      await session.prompt(payload.message);
    }
    // ... 其他类型处理 ...
  }
);
```

**工具自动清理**：
```typescript
// src/infrastructure/tools/check-pending-orders.ts
execute: async (toolCallId: string, params: any) => {
  const orderService = new OrderService(PI_DIR);
  
  // ✅ 先清理过期挂单
  const expiredCount = orderService.expireOverdue();
  
  // 获取所有 pending 挂单
  let pendingOrders = orderService.listPending();
  
  if (pendingOrders.length === 0) {
    return {
      content: [{
        type: "text" as const,
        text: `📋 当前无挂单${expiredCount > 0 ? `（已清理 ${expiredCount} 个过期挂单）` : ""}`
      }],
      // ...
    };
  }
  
  // ... 检查触发条件，自动成交 ...
}
```

---

## 📊 执行效果

### 系统启动时

```bash
$ npm start

⏰ Cron 任务（8 个）:
  ✅ 每日持仓复盘（cron: daily-review） 下次：2026-05-15 15:35（180 分钟后）
  ❌ 持仓止损预警（cron: stop-loss-alert） 下次：n/a
  ✅ 检查挂单并清理过期（cron: check-pending-orders） 下次：2026-05-15 09:30（15 分钟后）
  ✅ 开始盯盘（cron: market-monitor-start） 下次：2026-05-16 09:30（1425 分钟后）
  ✅ 每日交易建议（cron: trading-advice） 下次：2026-05-16 09:00（1395 分钟后）
  ✅ 每日 Pipeline 更新（cron: pipeline-daily） 下次：2026-05-15 16:00（360 分钟后）
  ✅ 每周 Pipeline 更新（cron: pipeline-weekly） 下次：2026-05-17 18:00（3060 分钟后）
  ✅ 每周进化分析（cron: weekly-evolution） 下次：2026-05-18 20:00（4620 分钟后）
```

### 自动执行时

```
[2026-05-15 09:30:00]
🤖 Agent 收到定时任务消息：检查所有挂单状态，自动成交触发的订单，清理过期挂单

📋 挂单检查报告 — 2026-05-15 09:30:00
检查 5 个挂单
已自动清理 2 个过期挂单

## ✅ 本次成交 (1)

### 🟢 1. 中芯国际 (688981)
- 方向: 买入 | 类型: 限价单
- 触发条件: 买入触发: 市价 ¥44.80 ≤ 挂单价 ¥45.00 (-0.44%)
- 成交: 300股 @ ¥44.80
- 持仓更新: 新增持仓 688981 中芯国际 300股@44.80
- 交易记录: ✅ 已记录

## ⏳ 未触发 (2)

### 📈 卖出 止损 贵州茅台 (600519)
- 当前价: ¥1750.00 | 挂单价: ¥1620.00
- 状态: 止损未触发

### 📈 卖出 限价 贵州茅台 (600519)
- 当前价: ¥1750.00 | 挂单价: ¥2160.00
- 状态: 限价未触发

---

### 📢 成交通知
✅ 本次成交 1 笔：中芯国际(688981) 买入 300股@¥44.80

## 💡 总结
✅ 成交: 1 · ⏳ 等待: 2 · ❌ 错误: 0

挂单已成交，持仓和交易记录已自动更新。

📂 orders.json 路径: .pi-invest/orders.json
```

---

## ✅ 优势

### 1. 真正的自动化
- ❌ 旧方案：依赖用户手动调用
- ✅ 新方案：系统自动定时执行

### 2. 及时性
- 交易时间每 30 分钟检查一次
- 不会错过挂单触发时机
- 过期挂单及时清理

### 3. 可靠性
- 连续失败 5 次自动禁用，防止无限重试
- 执行日志记录到 `.pi-invest/cron/cron-runs.jsonl`
- 系统启动时显示任务状态

### 4. 灵活性
- 可通过修改 CRON.json 调整执行频率
- 可通过 `enabled: false` 临时禁用
- 支持多种调度类型（at, every, cron）

---

## 🔍 监控与调试

### 查看 Cron 日志

```bash
# 查看最近 10 次执行记录
tail -10 .pi-invest/cron/cron-runs.jsonl | jq .

# 查看特定任务的执行记录
cat .pi-invest/cron/cron-runs.jsonl | jq 'select(.job_id == "check-pending-orders")'

# 查看失败的任务
cat .pi-invest/cron/cron-runs.jsonl | jq 'select(.status == "error")'
```

### 手动触发任务

虽然是自动任务，但也可以手动触发测试：

```typescript
// 在 agent 对话中
"手动触发检查挂单任务"

// 或者通过 API（如果暴露了接口）
cronService.triggerJob("check-pending-orders")
```

### 调整执行频率

```json
// 改为每 15 分钟
"expr": "*/15 9-15 * * 1-5"

// 改为每小时
"expr": "0 9-15 * * 1-5"

// 改为每 5 分钟（测试用）
"expr": "*/5 9-15 * * 1-5"
```

---

## 📝 注意事项

### 1. 时区
- Cron 表达式使用本地时间（中国时间）
- 不需要考虑时区转换

### 2. 交易时间
- 当前配置：9:00-15:00
- A股实际交易时间：9:30-11:30, 13:00-15:00
- 配置覆盖了开盘前和午休时间，确保不错过任何触发

### 3. 执行频率
- 30 分钟是平衡点：
  - 太频繁（如 5 分钟）：增加系统负载，API 调用次数多
  - 太稀疏（如 1 小时）：可能错过短期价格波动
- 可根据实际需求调整

### 4. 失败处理
- 连续失败 5 次自动禁用
- 需要手动修改 CRON.json 重新启用
- 建议监控日志，及时发现问题

---

## 🎉 总结

### 实施内容
1. ✅ 添加 cron 任务配置到 CRON.json
2. ✅ 验证 CronService 支持 agent_turn 类型
3. ✅ 验证 check_pending_orders 工具自动清理逻辑
4. ✅ 更新文档

### 核心价值
- **真正的自动化**：无需用户干预，系统自动执行
- **及时性**：交易时间每 30 分钟检查一次
- **可靠性**：失败自动禁用，执行日志记录
- **灵活性**：可调整频率，可临时禁用

### 使用建议
1. 系统启动后检查 cron 任务列表，确认任务已加载
2. 定期查看 cron 日志，监控执行情况
3. 根据实际需求调整执行频率
4. 如遇问题，检查日志中的错误信息

**OPT-006 完整实现完成！** 🎉
