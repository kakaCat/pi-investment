# Agent × 通知模板系统 业务场景设计

**日期**: 2026-08-14  
**目标**: 展示 Agent 如何动态使用和创建通知模板

---

## 🎯 核心理念

**Agent 不仅是模板的使用者，更是模板的创造者和优化者**

```
Agent 观察 → 学习有效模式 → 创建/优化模板 → 应用到通知 → 收集反馈 → 持续改进
```

---

## 📋 业务场景 1: 每日盘前报告

### 场景描述

**时间**: 每天早上 08:00  
**触发**: Agent OS 定时任务唤醒 Agent  
**任务**: 生成并发送盘前准备报告

---

### 流程设计

#### Step 1: Agent 被唤醒

```typescript
// Agent OS Scheduler 触发
const task = {
  type: 'scheduled',
  code: 'daily_premarket_report',
  time: '08:00',
  prompt: '生成今日盘前准备报告并发送到交易群'
};

// Agent 接收任务
agent.handleTask(task);
```

---

#### Step 2: Agent 收集数据

```typescript
// Agent 调用工具收集数据
const marketData = await agent.callTool('market_status', {});
const poolChanges = await agent.callTool('pool_manage', { action: 'changes' });
const signals = await agent.callTool('signal_scan', { timeframe: 'today' });
const portfolio = await agent.callTool('portfolio_status', {});
const riskAlerts = await agent.callTool('risk_check', {});

// Agent 整合数据
const reportData = {
  date: '2026-08-14',
  market_status: marketData.status,  // 'open' / 'closed'
  data_integrity: 'normal',
  pools_count: 5,
  last_update: '07:55',
  
  opportunities: signals.filter(s => s.confidence > 0.75).map(s => ({
    symbol: s.symbol,
    name: s.name,
    reason: s.reason,
    confidence: s.confidence
  })),
  
  alerts: riskAlerts.map(a => ({
    title: a.title,
    message: a.message,
    severity: a.severity
  })),
  
  cash: portfolio.cash,
  holdings_count: portfolio.holdings.length,
  
  pool_changes: poolChanges.map(c => ({
    pool_name: c.pool_name,
    added: c.added,
    removed: c.removed,
    reason: c.reason
  }))
};
```

---

#### Step 3: Agent 查询合适的模板

```typescript
// Agent 调用工具查询模板
const templates = await agent.callTool('notification_template_search', {
  type: 'daily_report',
  context: 'premarket'
});

// Agent 决策使用哪个模板
// 情况 A: 找到现有模板
if (templates.length > 0) {
  const selectedTemplate = agent.selectBestTemplate(templates, reportData);
  
  // 使用现有模板
  await agent.callTool('notification_send_template', {
    channel: 'trading',
    template_code: selectedTemplate.code,
    variables: reportData
  });
}

// 情况 B: 没有合适的模板，Agent 创建新模板
else {
  const newTemplate = await agent.createTemplate(reportData);
  
  // 保存模板到数据库
  await agent.callTool('notification_template_create', {
    code: 'premarket_report_v1',
    name: '盘前准备报告',
    template: newTemplate
  });
  
  // 使用新创建的模板
  await agent.callTool('notification_send_template', {
    channel: 'trading',
    template_code: 'premarket_report_v1',
    variables: reportData
  });
}
```

---

#### Step 4: Agent 生成的模板内容

```json
{
  "code": "premarket_report_v1",
  "name": "盘前准备报告",
  "template": {
    "title": "🌅 盘前准备 - {{date}}",
    "color": "blue",
    "sections": [
      {
        "title": "✅ 数据检查",
        "condition": "always",
        "fields": [
          "数据完整性: {{data_integrity}}",
          "股票池: {{pools_count}}个",
          "最新更新: {{last_update}}"
        ]
      },
      {
        "title": "💡 今日机会",
        "condition": "opportunities.length > 0",
        "content": "{{#each opportunities}}\n• {{symbol}} {{name}}: {{reason}} (置信度 {{confidence}}%)\n{{/each}}"
      },
      {
        "title": "📊 股票池变化",
        "condition": "pool_changes.length > 0",
        "content": "{{#each pool_changes}}\n**{{pool_name}}**:\n  新增: {{added.join(', ')}}\n  移除: {{removed.join(', ')}}\n  原因: {{reason}}\n{{/each}}"
      },
      {
        "title": "⚠️ 风险提示",
        "condition": "alerts.length > 0",
        "content": "{{#each alerts}}\n• {{title}}: {{message}}\n{{/each}}"
      },
      {
        "title": "📊 持仓状况",
        "condition": "always",
        "fields": [
          "可用资金: ¥{{cash}}",
          "持仓数: {{holdings_count}}只"
        ]
      }
    ]
  },
  "variables": [
    "date", "data_integrity", "pools_count", "last_update",
    "opportunities", "pool_changes", "alerts", "cash", "holdings_count"
  ],
  "metadata": {
    "created_by": "agent",
    "created_at": "2026-08-14 08:00:15",
    "use_count": 1,
    "success_rate": 1.0
  }
}
```

---

#### Step 5: 实际发送的消息

```
┌─────────────────────────────────────┐
│  🌅 盘前准备 - 2026-08-14          │
├─────────────────────────────────────┤
│  **✅ 数据检查**                    │
│  数据完整性: 正常                   │
│  股票池: 5个                        │
│  最新更新: 07:55                    │
│                                     │
│  **💡 今日机会**                    │
│  • 600519.SH 贵州茅台: 技术面突破   │
│    (置信度 85%)                     │
│  • 000858.SZ 五粮液: 超卖反弹       │
│    (置信度 78%)                     │
│                                     │
│  **📊 股票池变化**                  │
│  **白酒池**:                        │
│    新增: 600809.SH                  │
│    移除: 000568.SZ                  │
│    原因: ROE 低于 15% 阈值          │
│                                     │
│  **⚠️ 风险提示**                    │
│  • 大盘走势: 昨日下跌 1.2%，需谨慎 │
│                                     │
│  **📊 持仓状况**                    │
│  可用资金: ¥200,000.00              │
│  持仓数: 10只                       │
└─────────────────────────────────────┘
```

---

## 📋 业务场景 2: 交易信号实时告警

### 场景描述

**触发**: Agent 实时监控发现买入信号  
**任务**: 立即发送告警通知

---

### 流程设计

#### Step 1: Agent 发现信号

```typescript
// Agent 在实时监控中发现信号
const signal = {
  symbol: '600519.SH',
  name: '贵州茅台',
  action: 'buy',
  price: 1205.00,
  confidence: 0.82,
  triggers: [
    'MA5突破MA20（金叉）',
    'MACD柱状图转正',
    '成交量放大30%'
  ],
  suggested_shares: 100,
  expected_return: 0.08,
  stop_loss: 1150.00
};
```

---

#### Step 2: Agent 判断紧急程度

```typescript
// Agent 分析信号紧急程度
const urgency = agent.assessUrgency(signal);
// urgency = 'high' (因为置信度 82% > 80%)

// Agent 决定使用什么风格的模板
const templateType = urgency === 'high' ? 'trade_alert_urgent' : 'trade_alert_normal';
```

---

#### Step 3: Agent 查找或创建模板

```typescript
// 查找现有模板
let template = await agent.callTool('notification_template_get', {
  code: 'trade_alert_urgent'
});

// 如果不存在，Agent 创建一个
if (!template) {
  template = await agent.callTool('notification_template_create', {
    code: 'trade_alert_urgent',
    name: '紧急交易信号',
    template: {
      title: '🚨 交易信号触发',
      color: 'red',
      sections: [
        {
          title: '📈 信号详情',
          fields: [
            '股票: {{symbol}} {{name}}',
            '信号: {{action_text}}',
            '价格: ¥{{price}}',
            '置信度: {{confidence}}%'
          ]
        },
        {
          title: '🎯 触发原因',
          content: '{{#each triggers}}\n• {{this}}\n{{/each}}'
        },
        {
          title: '💰 建议操作',
          fields: [
            '买入数量: {{suggested_shares}}股',
            '预期收益: +{{expected_return_pct}}%',
            '止损价: ¥{{stop_loss}}'
          ]
        }
      ]
    }
  });
}
```

---

#### Step 4: Agent 发送通知

```typescript
await agent.callTool('notification_send_template', {
  channel: 'alerts',  // 发送到告警群（高优先级）
  template_code: 'trade_alert_urgent',
  variables: {
    symbol: signal.symbol,
    name: signal.name,
    action_text: '买入信号',
    price: signal.price.toFixed(2),
    confidence: (signal.confidence * 100).toFixed(0),
    triggers: signal.triggers,
    suggested_shares: signal.suggested_shares,
    expected_return_pct: (signal.expected_return * 100).toFixed(1),
    stop_loss: signal.stop_loss.toFixed(2)
  },
  urgency: 'high'
});
```

---

## 📋 业务场景 3: Agent 优化模板（自我进化）

### 场景描述

**触发**: Agent 定期分析通知效果  
**任务**: 优化不佳的模板

---

### 流程设计

#### Step 1: Agent 分析模板效果

```typescript
// 每周日晚上，Agent 分析过去一周的通知效果
const templateStats = await agent.callTool('notification_template_stats', {
  date_range: 'last_7_days'
});

// 结果示例
const stats = [
  {
    code: 'premarket_report_v1',
    use_count: 7,
    success_rate: 1.0,      // 100% 发送成功
    avg_feedback: null      // 暂无用户反馈
  },
  {
    code: 'trade_alert_urgent',
    use_count: 15,
    success_rate: 0.93,     // 93% 成功（有 1 次失败）
    avg_feedback: 4.2       // 用户评分 4.2/5
  },
  {
    code: 'daily_summary_v2',
    use_count: 7,
    success_rate: 0.71,     // 71% 成功（有 2 次失败）
    avg_feedback: 3.1       // 用户评分 3.1/5 (较低)
  }
];
```

---

#### Step 2: Agent 识别问题模板

```typescript
// Agent 识别表现不佳的模板
const poorTemplates = stats.filter(t => 
  t.success_rate < 0.8 || (t.avg_feedback && t.avg_feedback < 3.5)
);

// poorTemplates = [{ code: 'daily_summary_v2', ... }]
```

---

#### Step 3: Agent 分析失败原因

```typescript
// Agent 查询失败日志
const failedLogs = await agent.callTool('notification_logs_query', {
  template_code: 'daily_summary_v2',
  status: 'failed',
  date_range: 'last_7_days'
});

// Agent 分析失败原因
const analysis = agent.analyzeLogs(failedLogs);
// 发现：消息内容过长，超过飞书 28000 字符限制

// Agent 推理
agent.think(`
模板 daily_summary_v2 的问题：
1. 包含了太多详细持仓信息
2. 当持仓数量 > 15 只时，消息长度超过限制
3. 导致发送失败

优化方案：
1. 只显示前 10 只持仓
2. 其余的显示汇总信息
3. 提供"查看完整报告"链接
`);
```

---

#### Step 4: Agent 创建优化版本

```typescript
// Agent 创建新版本模板
await agent.callTool('notification_template_create', {
  code: 'daily_summary_v3',
  name: '每日总结报告 v3 (优化版)',
  template: {
    title: '📊 每日投资报告 - {{date}}',
    color: 'blue',
    sections: [
      {
        title: '💰 持仓表现',
        fields: [
          '总资产: ¥{{total_assets}}',
          '总盈亏: {{total_pnl}} ({{total_pnl_pct}}%)'
        ]
      },
      {
        title: '📊 Top 10 持仓',
        condition: 'holdings.length > 0',
        content: '{{#each top_holdings}}\n{{index}}. {{symbol}} {{name}}: {{pnl_pct}}%\n{{/each}}',
        footer: '{{#if has_more}}查看完整报告: {{report_url}}{{/if}}'
      },
      {
        title: '📈 交易情况',
        fields: [
          '今日交易: {{trades_today}}笔',
          '买入: {{buy_count}}笔',
          '卖出: {{sell_count}}笔'
        ]
      }
    ]
  },
  metadata: {
    created_by: 'agent',
    optimization_from: 'daily_summary_v2',
    optimization_reason: '解决消息过长问题',
    changes: [
      '只显示 Top 10 持仓',
      '添加完整报告链接',
      '减少详细信息'
    ]
  }
});

// Agent 停用旧版本
await agent.callTool('notification_template_update', {
  code: 'daily_summary_v2',
  enabled: false,
  metadata: {
    deprecated: true,
    deprecated_reason: '消息过长导致发送失败',
    replaced_by: 'daily_summary_v3'
  }
});
```

---

#### Step 5: Agent 更新通知规则

```typescript
// Agent 更新定时任务使用新模板
await agent.callTool('notification_rule_update', {
  code: 'daily_report_evening',
  template_code: 'daily_summary_v3'  // 从 v2 改为 v3
});

// Agent 记录优化日志
await agent.callTool('evolution_record', {
  type: 'template_optimization',
  action: 'replace',
  from: 'daily_summary_v2',
  to: 'daily_summary_v3',
  reason: '解决消息过长问题，成功率从 71% 提升到预期 95%+',
  expected_improvement: {
    success_rate: 0.95,
    user_satisfaction: 4.0
  }
});
```

---

## 🔧 Agent 工具接口设计

### 1. 查询模板

```typescript
// Tool: notification_template_search
{
  name: 'notification_template_search',
  description: '搜索通知模板',
  parameters: {
    type: 'keyword' | 'context',
    query: string,
    enabled_only: boolean
  },
  returns: Array<Template>
}
```

### 2. 创建模板

```typescript
// Tool: notification_template_create
{
  name: 'notification_template_create',
  description: '创建新的通知模板',
  parameters: {
    code: string,
    name: string,
    template: TemplateDefinition,
    metadata: Record<string, any>
  },
  returns: { template_id: string }
}
```

### 3. 使用模板发送

```typescript
// Tool: notification_send_template
{
  name: 'notification_send_template',
  description: '使用模板发送通知',
  parameters: {
    channel: string,
    template_code: string,
    variables: Record<string, any>,
    urgency?: 'low' | 'normal' | 'high' | 'critical'
  },
  returns: { log_id: string, success: boolean }
}
```

### 4. 查询模板统计

```typescript
// Tool: notification_template_stats
{
  name: 'notification_template_stats',
  description: '查询模板使用统计',
  parameters: {
    template_code?: string,
    date_range: string
  },
  returns: Array<{
    code: string,
    use_count: number,
    success_rate: number,
    avg_feedback?: number
  }>
}
```

### 5. 查询通知日志

```typescript
// Tool: notification_logs_query
{
  name: 'notification_logs_query',
  description: '查询通知发送日志',
  parameters: {
    template_code?: string,
    channel?: string,
    status?: 'pending' | 'sent' | 'failed',
    date_range: string
  },
  returns: Array<NotificationLog>
}
```

---

## 🎯 关键设计点

### 1. **Agent 是模板的主人**

- ✅ Agent 根据场景创建模板
- ✅ Agent 根据数据决定使用哪个模板
- ✅ Agent 根据效果优化模板

### 2. **模板是数据驱动的**

- ✅ 模板存储在数据库
- ✅ 支持条件渲染（if/each）
- ✅ 支持变量替换

### 3. **闭环优化**

```
Agent 发送通知
    ↓
记录日志（成功率、用户反馈）
    ↓
Agent 分析效果
    ↓
Agent 优化模板
    ↓
重新应用
```

### 4. **版本管理**

- ✅ 模板有版本（v1, v2, v3...）
- ✅ 旧版本可以停用但不删除
- ✅ 可以追溯优化历史

---

## 💡 额外场景：用户反馈驱动优化

### 场景：用户不喜欢某个模板

```
用户在飞书回复: "这个报告太长了，能简短点吗？"
    ↓
飞书 Bot 接收到消息
    ↓
Agent 分析反馈
    ↓
Agent 识别是对 daily_summary_v3 的反馈
    ↓
Agent 创建 daily_summary_v4（更简短）
    ↓
Agent 询问用户: "我创建了一个更简短的版本，要试试吗？"
    ↓
用户确认
    ↓
Agent 更新规则使用 v4
```

---

## ✅ 总结

### **Agent × 模板系统的打通方式**

1. **Agent 使用模板**: 通过 `notification_send_template` 工具
2. **Agent 创建模板**: 通过 `notification_template_create` 工具
3. **Agent 优化模板**: 分析日志 → 创建新版本 → 更新规则
4. **Agent 响应反馈**: 用户反馈 → Agent 调整 → 生成新模板

### **核心价值**

- ✅ **自动化**: Agent 自动创建和优化模板，无需人工维护
- ✅ **智能化**: Agent 根据场景和数据选择最合适的模板
- ✅ **进化性**: Agent 通过反馈不断优化模板质量
- ✅ **灵活性**: 用户可以通过自然语言指导 Agent 调整模板

---

**这个设计是否符合你的期望？需要调整哪些地方？**
