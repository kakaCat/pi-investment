# 早盘分析数据不一致根本原因分析

**日期**: 2026-08-25  
**问题**: 用户提供的早盘分析数据与数据库不一致  
**严重程度**: P0（系统性架构问题）

---

## 问题现象

用户在飞书中提供了一段"早盘分析"文本：
```
🌅 早盘分析完成 - agent_virtual (2026-08-25)
📊 账户概览（8/25 09:35）
- 总资产：¥104,007（+1.14%）
- 累计收益率：+4.01%

📋 持仓 3/3
- 格力 000651 +3.15%（20天）
- 杭行 600926 余200股 +7.46%（29天）
- 中免 601888 400股 +0.86%（1天）
```

但数据库实际状态：
- 总资产：¥105,029.71（+5.03%）
- 持仓：仅歌尔股份 002241（1300股，+2.38%）

**初始假设**：用户手动输入了错误数据。

**实际真相**：Agent 根本没有生成这段分析，因为**早盘分析任务从未执行过**。

---

## 调查过程

### 步骤1：确认早盘分析的来源

查看 `agent-decision-tasks.ts`，发现早盘分析应该由 `morning_ai_analysis` 任务生成：
```typescript
{
  name: 'morning_ai_analysis',
  enabled: true,
  scheduleKind: 'cron',
  scheduleExpr: '0 9 * * 1-5',  // 工作日 9:00
  payload: {
    kind: 'agent_turn',
    message: '🌅 早盘分析任务...'
  }
}
```

该任务明确要求：
```
第一步：检查持仓（唯一账本 agent_virtual）
使用 portfolio_status({ action: 'get', account: 'agent_virtual' }) 查看
```

### 步骤2：检查任务是否执行

查询 quantsys-v2 调度记录：
```sql
SELECT * FROM quant.scheduler_runs 
WHERE started_at::date = '2026-08-25'
  AND started_at::time BETWEEN '08:55' AND '09:10';
```

结果：
```
id   | task_name           | status  | started_at
-----|---------------------|---------|---------------------------
2970 | signal_generate_buy | success | 2026-08-25 09:00:00
```

**发现**：只有 `signal_generate_buy` 执行了，没有 `morning_ai_analysis`。

### 步骤3：检查任务是否注册

查询 Agent OS 调度器：
```bash
$ cd agent-os && ./agent-os scheduler list
```

结果：
```
ID        NAME                           SCHEDULE       ENABLED
57f75565  chan_knowledge_distill_weekly  0 12 * * 0     true
fb728559  chan_scan_daily                10 10 * * 1-5  true
9f3c44f1  signal_generate_buy            0 9 * * 1-5    true
...
# 没有 morning_ai_analysis
```

**发现**：Agent OS 中只有 quantsys-v2 的数据处理任务，缺少所有 Agent AI 决策任务。

### 步骤4：检查 agent-ts 启动状态

```bash
$ ps aux | grep agent.*headless
# 返回空
```

**发现**：agent-ts headless 进程没有运行。

---

## 根本原因

### 核心问题：agent-ts 服务未启动

**预期架构**：
```
agent-ts (headless) ──注册任务──→ Agent OS Scheduler
    ↓                                ↓
  持续运行                        定时触发
    ↓                                ↓
  接收 webhook                    执行 Agent AI 任务
    ↓                                ↓
  执行 Agent turn              调用 agent-ts webhook
```

**实际状态**：
```
agent-ts (headless) ❌ 未运行
    ↓
  任务注册代码从未执行
    ↓
  Agent OS 中没有 Agent AI 任务
    ↓
  早盘分析任务从未执行
```

### 7个缺失的任务

所有定义在 `createAgentDecisionTasks()` 中的任务都未注册：

1. **morning_ai_analysis** (09:00) - 早盘分析 + 虚拟仓交易
2. **realtime_quick_check** (每30分钟) - 盘中快速检查
3. **daily_ai_review** (18:00) - 每日复盘 + 绩效评估
4. **weekly_evolution** (周日 20:00) - 每周进化分析
5. **weekly_tool_roi_review** (周日 19:00) - 工具 ROI 审查
6. **weekly_memory_distill** (周日 21:00) - 记忆蒸馏
7. **daily_recall_audit** (19:00) - 召回质量审计

### 为什么 agent-ts 没有运行？

可能原因：
1. **从未启动过** - 部署后遗漏启动步骤
2. **启动失败** - 启动时报错但没有监控
3. **已崩溃** - 启动后崩溃，没有自动重启
4. **被手动停止** - 维护后忘记重启

---

## 影响范围

### 直接影响

| 功能 | 状态 | 影响 |
|------|------|------|
| 早盘分析 | ❌ 不可用 | 用户无法获得自动早盘分析 |
| 盘中监控 | ❌ 不可用 | 市场异常无法及时发现 |
| 每日复盘 | ❌ 不可用 | 无法自动评估交易绩效 |
| 每周进化 | ❌ 不可用 | 策略优化建议不产生 |
| 工具优化 | ❌ 不可用 | 低效工具无法识别 |
| 记忆蒸馏 | ❌ 不可用 | 经验无法提炼为规则 |
| 召回审计 | ❌ 不可用 | 记忆质量无法监控 |

### 系统性风险

1. **Agent 自主性丧失**
   - Agent 无法自主执行定时任务
   - 完全依赖用户手动触发
   - 系统退化为"被动响应工具"

2. **学习闭环断裂**
   - 无每日复盘 → 无绩效反馈
   - 无每周进化 → 无策略优化
   - 无记忆蒸馏 → 无经验积累

3. **数据可信度问题**
   - 用户以为系统在运行
   - 实际上核心功能全部失效
   - 可能基于错误假设做决策

---

## 修复方案

### 立即修复（今天）

**步骤1：检查启动脚本**

<function_calls>
<invoke name="Bash">
<parameter name="command">cat ~/scripts/pi-services.sh 2>/dev/null | head -50