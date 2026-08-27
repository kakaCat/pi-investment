# 从 Agent 视角审视通知系统设计

**日期**: 2026-08-14  
**目标**: 评估设计是否符合 Agent 的工作方式

---

## 🤔 核心问题

**Agent 对应内容都很多，程序模板是否合适？**

让我从 Agent 的实际工作流程来分析。

---

## 📊 场景分析：Agent 生成每日报告

### **Agent 的真实工作流程**

```
1. Agent 被唤醒
   ↓
2. Agent 理解任务："生成并发送每日报告"
   ↓
3. Agent 规划：
   - 需要什么数据？
   - 如何组织内容？
   - 发送到哪里？
   ↓
4. Agent 收集数据
   - 调用 market_status
   - 调用 portfolio_status
   - 调用 signal_scan
   - 调用 risk_check
   ↓
5. Agent 分析和思考
   - 哪些信息重要？
   - 如何表达更清楚？
   - 需要强调什么？
   ↓
6. Agent 生成内容（这里是关键！）
   ↓
7. Agent 发送
```

---

## 🎯 关键问题：第 6 步怎么做？

### **方式 A: 程序模板（我之前的设计）**

```typescript
// Agent 调用工具
await agent.call('notification_send_template', {
  channel: 'trading',
  template_code: 'daily_report',
  variables: {
    date: '2026-08-14',
    total_assets: 1050000,
    cash: 200000,
    holdings_count: 11,
    opportunities: [...]
  }
});
```

**Agent 的体验**:
```
Agent: "我有数据了，用 daily_report 模板发送"
系统: "好的，填充数据..."
系统: "发送完成"
Agent: ✅ 任务完成
```

**问题在哪里**？

1. **Agent 失去了控制权**
   - Agent 不能决定如何表达
   - Agent 不能根据数据调整重点
   - Agent 变成了"数据搬运工"

2. **Agent 的智能被浪费**
   - Agent 可以判断："今天机会很多，应该重点强调"
   - 但程序模板只会机械填充
   - Agent 的分析能力没用上

3. **内容太多怎么办**？
   ```typescript
   variables: {
     opportunities: [
       { symbol: '600519.SH', reason: '技术面突破，MA5上穿MA20...' },
       { symbol: '000858.SZ', reason: '超卖反弹，RSI...' },
       { symbol: '600809.SH', reason: '成交量放大...' },
       // ... 还有 10 个机会
     ]
   }
   ```
   
   程序模板会怎么做？
   ```
   💡 今日机会
   • 600519.SH: 技术面突破，MA5上穿MA20...
   • 000858.SZ: 超卖反弹，RSI...
   • 600809.SH: 成交量放大...
   • ... (还有 10 个)
   ```
   
   → 内容太长，用户看不过来！
   
   **Agent 能做得更好**:
   ```
   💡 今日机会
   
   🔥 重点关注（置信度 >85%）
   • 600519.SH 贵州茅台: 多重信号共振
     技术面：MA5上穿MA20（金叉）
     资金面：成交量放大 30%
     建议：优先配置
   
   📊 其他机会（12个）
   • 白酒板块 5 个，科技板块 4 个...
   详情请查看完整报告
   ```
   
   → Agent 做了**筛选、分类、突出重点**

---

### **方式 B: Agent 自由生成**

```typescript
// Agent 不用模板，自己生成
const content = await agent.generate(`
我收集了以下数据：
${JSON.stringify(allData)}

请生成今日盘前报告，发送到交易群。
`);

await agent.call('notification_send', {
  channel: 'trading',
  title: '🌅 盘前准备',
  content: content
});
```

**Agent 的体验**:
```
Agent: "我分析了数据，发现..."
Agent: "今天有 13 个机会，但只有 2 个置信度很高"
Agent: "资金有点紧张，需要提醒"
Agent: "我生成一个突出重点的报告"
系统: "好的，发送完成"
Agent: ✅ 任务完成
```

**优点**:
- ✅ Agent 完全控制
- ✅ 智能筛选和突出
- ✅ 根据数据动态调整

**缺点**:
- ❌ 每次都要 LLM 生成（慢、贵）
- ❌ 格式可能不一致
- ❌ 可能遗漏重要信息

---

### **方式 C: 混合方式（Agent 提示词模板）**

```typescript
// 提示词模板（引导 Agent）
const promptTemplate = `
生成今日盘前报告。

数据已收集：
- 机会列表: {{opportunities}} (共 {{opportunities.length}} 个)
- 风险列表: {{risks}}
- 持仓情况: {{portfolio}}

生成要求：
1. 如果机会 >10 个，只突出置信度 >80% 的，其余汇总
2. 如果资金 <10万，强调风险控制
3. 如果有紧急风险，放在最前面
4. 用飞书卡片 Markdown 格式
5. 总长度控制在 500 字以内

输出格式：
标题: 🌅 盘前准备 - {{date}}
内容: [你自由发挥]
`;

await agent.call('generate_with_prompt_template', {
  template_code: 'premarket_report_guided',
  variables: allData,
  channel: 'trading'
});
```

**Agent 的体验**:
```
Agent: "我要生成报告"
系统: "这是提示词模板，告诉你要注意什么"
Agent: "好的，我看到了：机会多时要筛选，资金紧张要提醒..."
Agent: "我生成一个符合要求的报告"
系统: "发送完成"
Agent: ✅ 任务完成
```

**优点**:
- ✅ Agent 有控制权
- ✅ 有指导规范（不会乱来）
- ✅ 智能+规范平衡

**缺点**:
- ❌ 还是要 LLM 生成（有成本）
- ⚠️ 需要维护提示词模板

---

## 🔍 深入问题：Agent 对应内容都很多

### **问题场景**

```typescript
// Agent 收集到的数据
const data = {
  opportunities: [
    // 13 个投资机会
  ],
  risks: [
    // 5 个风险点
  ],
  portfolio: {
    holdings: [
      // 11 只持仓
    ],
    performance: [
      // 每只股票的表现
    ]
  },
  pool_changes: [
    // 5 个股票池的变化
  ],
  market_news: [
    // 8 条市场新闻
  ]
};
```

### **程序模板的问题**

```typescript
// 程序模板会机械输出所有内容
const template = `
💡 今日机会（13个）
{{#each opportunities}}
• {{symbol}} {{name}}: {{reason}}
{{/each}}

⚠️ 风险提示（5个）
{{#each risks}}
• {{title}}: {{message}}
{{/each}}

📊 持仓表现（11只）
{{#each holdings}}
• {{symbol}}: {{pnl_pct}}%
{{/each}}

...
`;
```

**结果**:
- ❌ 消息太长（可能超过飞书限制）
- ❌ 用户看不过来
- ❌ 没有重点

### **Agent 生成的优势**

```typescript
// Agent 会智能处理
Agent 思考:
"13 个机会太多了，我只突出 Top 3"
"5 个风险中，有 2 个是紧急的，放前面"
"11 只持仓，只展示涨跌幅 >5% 的"
"市场新闻只提关键的 1-2 条"

Agent 生成:
"""
🌅 盘前准备 - 2026-08-14

🔥 重点关注（Top 3）
1. 600519.SH 贵州茅台 - 多重信号共振（置信度 85%）
2. 000858.SZ 五粮液 - 超卖反弹（置信度 78%）
3. 600809.SH 山西汾酒 - 突破关键阻力（置信度 76%）

⚠️ 紧急风险
• 大盘昨日跌 1.2%，今日需谨慎
• 可用资金 ¥8.5万，接近预警线

📊 持仓异动
• 000001.SZ 平安银行: +6.2% 🎉
• 600036.SH 招商银行: -5.1% ⚠️

💡 其他机会
还有 10 个机会，详情见完整报告链接
"""
```

**Agent 做了什么**？
1. ✅ 筛选：13 → 3（Top 机会）
2. ✅ 排序：紧急风险优先
3. ✅ 过滤：只显示异动持仓
4. ✅ 汇总：其他内容简化
5. ✅ 突出：用 emoji 标记重点

---

## 💡 设计反思

### **程序模板的适用场景**

只适合**简单、结构固定、数据少**的场景：

```typescript
// ✅ 适合：交易执行确认
{
  title: "✅ 交易执行成功",
  content: `
股票: ${symbol} ${name}
操作: ${action}
数量: ${shares}股
价格: ¥${price}
  `
}
// 数据少、格式固定、不需要智能
```

### **Agent 生成的适用场景**

适合**复杂、数据多、需要判断**的场景：

```typescript
// ✅ 适合：每日报告
- 数据来源多（市场、持仓、信号、风险...）
- 数据量大（几十个数据点）
- 需要筛选和突出重点
- 需要根据情况调整表达
```

---

## 🎯 重新设计：Agent 优先

### **新架构**

```
┌─────────────────────────────────────┐
│  触发层                              │
│  - 定时任务                          │
│  - 事件触发                          │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Agent 层（核心）                    │
│  - 收集数据                          │
│  - 分析判断                          │
│  - 智能生成内容                      │
│  - 决定发送方式                      │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  通知层（工具）                      │
│  - notification_send_simple()        │
│  - notification_send_rich()          │
│  - notification_send_card()          │
└─────────────────────────────────────┘
```

### **Agent 工具设计**

```typescript
// 工具 1: 简单发送（Agent 已生成好内容）
{
  name: 'notification_send',
  description: '发送通知消息（你已经生成好内容）',
  parameters: {
    channel: string,      // 'trading', 'alerts'
    title: string,        // 标题
    content: string,      // 内容（Markdown）
    color?: string,       // 'blue', 'red', 'green'
    urgency?: string      // 'low', 'normal', 'high'
  }
}

// 工具 2: 结构化发送（Agent 提供结构化数据）
{
  name: 'notification_send_structured',
  description: '发送结构化通知（我帮你渲染）',
  parameters: {
    channel: string,
    template_type: string,  // 'simple', 'list', 'comparison', 'alert'
    data: {
      title: string,
      sections: Array<{
        title: string,
        items: string[],
        highlight?: boolean
      }>
    }
  }
}

// 工具 3: 查询历史（Agent 学习）
{
  name: 'notification_history',
  description: '查询过去的通知，学习什么样的消息效果好',
  parameters: {
    channel?: string,
    date_range: string,
    with_feedback: boolean  // 是否包含用户反馈
  }
}
```

### **Agent 使用示例**

```typescript
// Agent 收集数据
const opportunities = await agent.call('signal_scan');
const portfolio = await agent.call('portfolio_status');
const risks = await agent.call('risk_check');

// Agent 分析和生成
agent.think(`
我收集到了：
- 13 个投资机会
- 5 个风险点
- 11 只持仓

用户不需要看所有细节，我应该：
1. 只突出最重要的 2-3 个机会
2. 如果有紧急风险，优先展示
3. 持仓只显示大幅波动的
4. 用简洁的语言
`);

// Agent 生成内容
const reportContent = await agent.generate(`
基于以下数据生成盘前报告：
- 机会: ${JSON.stringify(opportunities.slice(0, 5))}
- 风险: ${JSON.stringify(risks)}
- 持仓: ${JSON.stringify(portfolio)}

要求：
1. 突出 Top 3 机会
2. 紧急风险优先
3. 持仓只显示波动 >5% 的
4. 总长度 <500 字
5. 用 Markdown 格式
`);

// Agent 发送
await agent.call('notification_send', {
  channel: 'trading',
  title: '🌅 盘前准备',
  content: reportContent,
  color: 'blue'
});

// Agent 记录（用于学习）
await agent.call('memory_write', {
  type: 'notification',
  content: '今日盘前报告已发送，突出了白酒板块机会',
  metadata: {
    opportunities_count: 13,
    highlighted: 3,
    channel: 'trading'
  }
});
```

---

## ✅ 结论

### **程序模板不适合 Agent 的原因**

1. ❌ **剥夺了 Agent 的控制权**
   - Agent 变成数据搬运工
   - Agent 的智能被浪费

2. ❌ **无法处理复杂情况**
   - 数据太多时机械输出
   - 不能筛选和突出重点
   - 不能根据情况调整

3. ❌ **不符合 Agent 的工作方式**
   - Agent 善于分析和判断
   - Agent 善于根据情况调整
   - 程序模板是死的，Agent 是活的

### **更好的设计**

1. ✅ **让 Agent 生成内容**
   - Agent 收集数据
   - Agent 分析判断
   - Agent 生成内容
   - Agent 调用工具发送

2. ✅ **提供指导而非限制**
   - 用"提示词模板"引导 Agent
   - 而不是用"程序模板"限制 Agent

3. ✅ **工具要简单**
   ```typescript
   // 好的工具设计
   notification_send(channel, title, content)
   
   // 不好的设计
   notification_send_template(template_id, variables)
   ```

---

## 🚀 最终设计

### **核心原则**

**Agent First**: Agent 是主角，工具是配角

```
Agent 决策 → Agent 生成 → Agent 发送
    ↑                           ↓
    └──────── 学习反馈 ──────────┘
```

### **实现方式**

1. **通知工具**: 简单的发送接口
2. **提示词引导**: 可选的指导（不强制）
3. **历史学习**: Agent 可以查询过去的通知效果
4. **用户反馈**: Agent 可以根据反馈调整

---

**这个分析是否解答了你的疑问？**
