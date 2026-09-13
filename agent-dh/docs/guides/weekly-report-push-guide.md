---
id: guides-weekly-report-push-guide
title: M6 周报推送使用指南
type: guide
status: living
updated: 2026-09-13
owners: [agent-dh]
tags: [guide]
---

# M6 周报推送使用指南

## 快速开始

### 1. 获取飞书 Webhook

1. 进入飞书群聊
2. **群设置** → **群机器人** → **添加机器人** → **自定义机器人**
3. 设置机器人名称（如"PI 投资周报"）
4. 复制 Webhook 地址（格式：`https://open.feishu.cn/open-apis/bot/v2/hook/...`）

### 2. 配置环境变量（可选）

```bash
export FEISHU_WEEKLY_REPORT_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/..."
```

### 3. 推送周报

#### 方式 A: 使用 API

```bash
# 推送本周周报
curl -X POST "http://localhost:5001/api/reports/weekly/push"

# 推送指定周周报
curl -X POST "http://localhost:5001/api/reports/weekly/push?week_start=2026-08-17&week_end=2026-08-23"

# 使用自定义 webhook
curl -X POST "http://localhost:5001/api/reports/weekly/push?feishu_webhook=https://..."
```

#### 方式 B: 使用 Agent 工具

在 DSH 投资 profile 中：

```typescript
// 推送周报
await ctx.tools.invoke('weekly_report_push', {
  feishu_webhook: 'https://open.feishu.cn/...'
});

// 推送指定周周报
await ctx.tools.invoke('weekly_report_push', {
  week_start: '2026-08-17',
  week_end: '2026-08-23',
  feishu_webhook: 'https://...'
});
```

#### 方式 C: 定时任务

配置 Agent OS Scheduler（每周五 18:00 自动推送）：

```yaml
# ~/.dsh/profiles/investment/scheduler.yml
jobs:
  - id: weekly_report_auto_push
    name: "每周五周报自动推送"
    schedule: "0 18 * * 5"  # 每周五 18:00
    enabled: true
    action:
      type: tool_call
      tool: weekly_report_push
      params: {}
```

---

## 周报内容

周报包含以下部分：

### 📊 本周概览
- 信号数量（总计/已回填）
- 5日胜率
- 5日平均收益
- 信号分级分布（A/B/C）

### 🎯 规则归因
- 本周活跃规则数量
- Top 3 规则表现（引用次数、胜率、平均收益）

### ✨ 本周亮点
- 信号质量评价
- 最佳规则表现
- Regime 变化（待实现）

### 💡 改进建议
- 建议强化的规则（高胜率高收益）
- 建议淘汰的规则（持续亏损）
- 继续观察的规则（样本不足）

---

## 常见问题

### Q1: 推送失败怎么办？

**A**: 检查以下项：
1. Webhook URL 是否正确
2. 飞书群机器人是否被移除
3. 网络连接是否正常
4. 查看错误信息：`curl -X POST ... | jq .data.push_result`

### Q2: 如何查看周报不推送？

**A**: 使用生成 API：

```bash
# Markdown 格式
curl "http://localhost:5001/api/reports/weekly/latest?format=markdown"

# JSON 格式
curl "http://localhost:5001/api/reports/weekly/latest"
```

### Q3: 如何推送历史周报？

**A**: 指定 `week_start` 和 `week_end` 参数：

```bash
curl -X POST "http://localhost:5001/api/reports/weekly/push?week_start=2026-08-10&week_end=2026-08-16"
```

### Q4: 周报数据从哪里来？

**A**: 数据来源：
- **信号统计**: `signal_tracking` 表（M3-1）
- **规则归因**: 从 `reason` 字段提取 R-xxx 规则引用（M6-1）
- **表现数据**: `return_5d/10d/20d` 和 `hit_5d/10d/20d` 字段

### Q5: 为什么胜率显示 N/A？

**A**: 可能原因：
1. 信号尚未回填表现（需等待 5/10/20 日后）
2. `return_5d` 字段为空（回填任务未运行）

---

## 测试验证

使用测试脚本验证功能：

```bash
cd /Users/yunpeng/pi-investment/agent-dh
./scripts/test-weekly-report-push.sh
```

---

## 相关文档

- [M6-3 周报推送交付](../work-logs/2026-09/m6-3-weekly-report-delivery.md)
- [M6-2 业绩归因交付](../work-logs/2026-09/m6-2-attribution-delivery.md)
- [M6-1 记忆检索接入核验](../work-logs/2026-08/m6-1-memory-search-integration-verification.md)

---

## 相关页面

- [M6-3 周报推送交付](../work-logs/2026-09/m6-3-weekly-report-delivery.md)
- [M6-2 业绩归因交付](../work-logs/2026-09/m6-2-attribution-delivery.md)
- [记忆与召回](../architecture/memory-and-recall.md)
