# 模板概念澄清：程序模板 vs Agent 提示词模板

**日期**: 2026-08-14  
**目标**: 澄清两种"模板"的区别和协作方式

---

## 🤔 两种"模板"

### **模板 A: 程序模板（填空模板）**

**本质**: 数据占位符，机械替换

```typescript
// 程序模板（死的）
const template = {
  title: "📊 每日报告 - {{date}}",
  content: "总资产: {{total_assets}}\n持仓: {{holdings_count}}只"
};

// 渲染
const message = render(template, {
  date: "2026-08-14",
  total_assets: 1050000,
  holdings_count: 11
});

// 结果（固定格式）
"📊 每日报告 - 2026-08-14
总资产: 1050000
持仓: 11只"
```

**特点**:
- ❌ 固定格式
- ❌ 没有智能
- ❌ 不能根据数据调整表达
- ✅ 快速、稳定、可预测

---

### **模板 B: Agent 提示词模板（生成模板）**

**本质**: 指导 LLM 生成内容的指令

```typescript
// Agent 提示词模板（活的）
const promptTemplate = `
你是一个投资助手，需要生成每日盘前报告。

数据:
- 日期: {{date}}
- 总资产: {{total_assets}}
- 持仓数: {{holdings_count}}
- 机会列表: {{opportunities}}

要求:
1. 用简洁专业的语言
2. 突出关键信息
3. 如果有高置信度机会，重点强调
4. 如果资金紧张，提醒注意风险
5. 根据市场情况调整语气

请生成飞书卡片格式的报告。
`;

// Agent 生成（智能的）
const message = await llm.generate(promptTemplate, variables);

// 结果（根据数据动态调整）
"📊 盘前准备 - 2026-08-14

🔥 今日重点关注
发现 2 个高置信度机会，建议优先关注 600519.SH

💰 资金状况
总资产 ¥105万，持仓 11 只
⚠️ 可用资金偏紧，建议谨慎加仓

💡 机会分析
1. 600519.SH 贵州茅台 - 技术面突破，成交量放大
   置信度 85%，建议关注..."
```

**特点**:
- ✅ 灵活表达
- ✅ 智能调整
- ✅ 根据数据重点突出
- ❌ 慢（需要 LLM 生成）
- ❌ 不稳定（每次结果略有不同）

---

## 🎯 你问的是哪个？

### **我之前设计的是：程序模板（模板 A）**

原因：
1. 快速稳定
2. 成本低
3. 格式一致

但这**忽略了 Agent 的智能**！

---

### **你期望的是：Agent 提示词模板（模板 B）**

让 Agent 智能生成内容，而不是机械填空。

---

## 🏗️ 正确的架构设计

### **方案 1: 纯 Agent 生成（推荐）**

```
触发 → Agent 收集数据 → Agent 用提示词生成消息 → 发送到飞书
```

**流程**:

```typescript
// 1. 定时任务触发
scheduler.trigger('daily_premarket_report');

// 2. Agent 被唤醒
agent.handleTask({
  type: 'generate_report',
  prompt: `
生成今日盘前准备报告，发送到交易群。

要求：
- 分析市场状况
- 列出投资机会
- 检查风险点
- 提醒持仓情况
- 用飞书卡片格式
`
});

// 3. Agent 调用工具收集数据
const data = {
  market: await agent.call('market_status'),
  signals: await agent.call('signal_scan'),
  portfolio: await agent.call('portfolio_status'),
  risks: await agent.call('risk_check')
};

// 4. Agent 分析数据并生成报告（这里才是"模板"）
agent.systemPrompt = `
你是 Pi Investment 助手。
生成报告时要：
1. 用 Markdown 格式
2. 突出 2-3 个最重要的点
3. 如果有高置信度机会（>80%），用 🔥 标记
4. 如果有风险，用 ⚠️ 标记
5. 语气专业但不生硬
`;

const report = await agent.generate(`
基于以下数据生成盘前报告：
${JSON.stringify(data, null, 2)}
`);

// 5. Agent 调用通知工具发送
await agent.call('notification_send', {
  channel: 'trading',
  title: '🌅 盘前准备',
  content: report,
  color: 'blue'
});
```

**优点**:
- ✅ 完全智能化
- ✅ Agent 根据数据动态调整
- ✅ 可以处理复杂场景
- ✅ 用户反馈可以直接影响生成

**缺点**:
- ⚠️ 慢（每次都要 LLM 生成）
- ⚠️ 成本高
- ⚠️ 结果不稳定

---

### **方案 2: 混合模式（平衡）**

**简单场景用程序模板，复杂场景用 Agent 生成**

```typescript
// 决策逻辑
if (isSimpleNotification(data)) {
  // 简单通知：用程序模板（快速）
  await sendWithTemplate('trade_executed', data);
} else {
  // 复杂报告：让 Agent 生成（智能）
  await agent.generateAndSend(data);
}
```

**示例**:

```typescript
// 场景 1: 交易执行确认（简单，用程序模板）
await notification.send('trading', {
  title: '✅ 交易执行成功',
  content: `
**股票**: ${symbol} ${name}
**操作**: ${action}
**数量**: ${shares}股
**价格**: ¥${price}
**总额**: ¥${total}
  `.trim()
});

// 场景 2: 每日深度分析（复杂，Agent 生成）
await agent.call('generate_and_send_report', {
  type: 'daily_analysis',
  channel: 'trading',
  prompt: `
分析今日市场表现，生成深度报告。
包括：
1. 市场整体走势分析
2. 板块轮动情况
3. 我们的持仓表现
4. 明日操作建议
数据：${JSON.stringify(data)}
  `
});
```

---

### **方案 3: Agent 提示词模板库（你真正想要的？）**

**核心**: 存储"提示词模板"，让 Agent 复用好的提示词

```sql
-- 提示词模板表
CREATE TABLE agent_prompt_templates (
    id UUID PRIMARY KEY,
    code VARCHAR(64) UNIQUE,
    name VARCHAR(100),
    category VARCHAR(32),  -- 'report', 'analysis', 'alert'
    prompt_template TEXT,  -- 提示词模板
    system_context TEXT,   -- 系统上下文
    output_format VARCHAR(32),  -- 'markdown', 'feishu_card'
    variables TEXT[],      -- 需要的变量
    examples JSONB,        -- Few-shot 示例
    metadata JSONB
);
```

**示例数据**:

```sql
INSERT INTO agent_prompt_templates (code, name, category, prompt_template, system_context, output_format, variables) VALUES (
  'daily_premarket_report',
  '每日盘前报告',
  'report',
  '基于以下数据生成今日盘前准备报告：

**市场状况**
状态: {{market_status}}
最新更新: {{last_update}}

**投资机会**
{{#each opportunities}}
- {{symbol}} {{name}}: {{reason}} (置信度 {{confidence}}%)
{{/each}}

**风险提示**
{{#each risks}}
- {{title}}: {{message}}
{{/each}}

**持仓情况**
可用资金: ¥{{cash}}
持仓数: {{holdings_count}}只

要求：
1. 用飞书卡片 Markdown 格式
2. 标题用 🌅 盘前准备
3. 如果有高置信度机会（>80%），用 🔥 突出显示
4. 如果资金紧张（<10万），用 ⚠️ 提醒
5. 语气专业简洁，重点突出',
  
  '你是 Pi Investment 助手，负责生成每日盘前准备报告。你的风格是：专业、简洁、重点突出。',
  
  'feishu_card',
  
  ARRAY['market_status', 'last_update', 'opportunities', 'risks', 'cash', 'holdings_count']
);
```

**Agent 使用**:

```typescript
// Agent 工具：使用提示词模板生成并发送
await agent.call('generate_with_prompt_template', {
  template_code: 'daily_premarket_report',
  variables: {
    market_status: 'open',
    last_update: '07:55',
    opportunities: [...],
    risks: [...],
    cash: 200000,
    holdings_count: 11
  },
  channel: 'trading'
});

// 背后发生的事情：
// 1. 从数据库加载提示词模板
// 2. 用变量渲染提示词
// 3. 调用 LLM 生成内容
// 4. 发送到指定渠道
```

**Agent 优化提示词**:

```typescript
// 每周 Agent 分析生成效果
const stats = await agent.call('prompt_template_stats', {
  template_code: 'daily_premarket_report',
  date_range: 'last_7_days'
});

// Agent 发现问题
if (stats.user_feedback < 4.0) {
  // Agent 分析用户反馈
  const feedback = await agent.call('get_user_feedback', {
    template_code: 'daily_premarket_report'
  });
  
  // Agent 推理改进
  agent.think(`
用户反馈："信息太多，看不到重点"
改进方向：
1. 减少详细信息
2. 只突出 Top 3 机会
3. 风险提示更简洁
  `);
  
  // Agent 创建优化版提示词
  await agent.call('prompt_template_create', {
    code: 'daily_premarket_report_v2',
    based_on: 'daily_premarket_report',
    improvements: [
      '只显示 Top 3 机会',
      '风险提示精简到 1-2 条',
      '整体长度控制在 200 字以内'
    ],
    prompt_template: `...优化后的提示词...`
  });
}
```

---

## 🎯 最终推荐架构

### **三层架构**

```
┌─────────────────────────────────────┐
│  业务层（定时任务/事件触发）         │
├─────────────────────────────────────┤
│  Agent 层（智能生成内容）            │
│  - 使用提示词模板                   │
│  - 调用工具收集数据                 │
│  - LLM 生成内容                     │
│  - 自我优化提示词                   │
├─────────────────────────────────────┤
│  通知层（统一发送接口）              │
│  - Provider 抽象                    │
│  - 飞书/Slack/邮件...              │
│  - 发送日志                         │
└─────────────────────────────────────┘
```

### **数据库设计**

```sql
-- 提示词模板（Agent 用来生成内容）
agent_prompt_templates

-- 通知渠道（发送目标）
notification_channels

-- 发送日志（追踪）
notification_logs

-- 用户反馈（优化依据）
notification_feedback
```

### **完整流程**

```
1. 定时任务触发
   ↓
2. Agent 被唤醒
   ↓
3. Agent 从数据库加载"提示词模板"
   ↓
4. Agent 调用工具收集数据
   ↓
5. Agent 用提示词 + 数据调用 LLM 生成内容
   ↓
6. Agent 调用通知工具发送
   ↓
7. 记录日志
   ↓
8. 收集用户反馈
   ↓
9. Agent 定期分析效果
   ↓
10. Agent 优化提示词模板
```

---

## ✅ 回答你的问题

### **Q: agent 的模版是提示词，和程序模版不一样？**

**A**: 是的！

- **程序模板** = 填空（机械替换）
- **Agent 提示词模板** = 指导 LLM 生成内容（智能创作）

### **Q: 你说的模版是哪个？**

**A**: 我之前说的是"程序模板"（填空）

但你想要的应该是：**Agent 提示词模板（智能生成）**

---

## 🚀 最终方案

### **混合使用**

```typescript
// 简单通知：程序模板（快速、稳定）
notification.send('trading', template('trade_executed', data));

// 复杂报告：Agent 生成（智能、灵活）
agent.generateAndSend({
  promptTemplate: 'daily_analysis',
  data: marketData,
  channel: 'trading'
});
```

### **提示词模板管理**

- ✅ 提示词存数据库
- ✅ Agent 可以查询和使用
- ✅ Agent 可以创建和优化
- ✅ 支持版本管理
- ✅ 记录生成效果

---

**现在清楚了吗？你希望实现的是哪种方案？**

1. 纯 Agent 生成（方案 1）
2. 混合模式（方案 2）
3. Agent 提示词模板库（方案 3）
