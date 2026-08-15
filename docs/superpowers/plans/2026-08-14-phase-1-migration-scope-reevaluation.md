# Phase 1 迁移范围重新评估报告

> **评估时间**: 2026-08-14  
> **目标**: 确定真正需要迁移的数据  
> **结论**: 大幅简化迁移范围

---

## 📊 v2 数据库现状

### 数据量统计

| 表名 | 数据量 | 用途 | 迁移建议 |
|---|---|---|---|
| **scheduler_runs** | 41 条 | 任务执行历史 | ❌ 不迁移 |
| **scheduler_tasks** | 6 条 | 任务定义 | ⚠️ 手动迁移 |
| **notification_logs** | 4 条 | 通知日志 | ❌ 不迁移 |
| **notification_channels** | 3 条 | 通知渠道 | ✅ 可选迁移 |
| **decisions** | 1 条 | 决策记录 | ✅ 迁移 |
| **notification_providers** | 1 条 | 通知提供商 | ✅ 可选迁移 |

### 不存在的表

| 表名 | 状态 | 说明 |
|---|---|---|
| **agent_memory** | ❌ 不存在 | Memory 功能未在 v2 实现 |
| **memory_tags** | ❌ 不存在 | Memory 功能未在 v2 实现 |

---

## 🎯 重新评估的迁移策略

### 策略变更

**原计划**（过度复杂）:
```
1. Memory 数据迁移 ← 不存在
2. Decision 数据迁移 ← 只有 1 条
3. Scheduler 任务迁移 ← 只有 6 条
4. Notification 数据迁移 ← 很少数据
```

**新策略**（务实简化）:
```
1. ✅ 手动迁移 scheduler_tasks（6 条任务定义）
2. ✅ 迁移 decisions（1 条，验证表结构）
3. ⏸️ Notification 数据：Agent OS 已有新配置，不迁移
4. ❌ Memory 数据：不存在，跳过
5. ❌ 历史执行记录：不迁移，从 Agent OS 重新开始
```

---

## 📋 简化后的迁移任务清单

### 任务 1: 迁移 Decisions 表（1 条数据）

**目的**: 验证表结构兼容性

**Step 1: 检查表结构差异**

```bash
# v2 结构
psql -d quant_investment -c "\d decisions"

# Agent OS 结构
psql -d agent_os -c "\d decisions"
```

**Step 2: 迁移数据**

```sql
-- 如果结构兼容，直接插入
INSERT INTO agent_os.public.decisions
SELECT * FROM quant_investment.public.decisions;
```

**工期**: 10 分钟

---

### 任务 2: 手动迁移 Scheduler Tasks（6 条任务）

**目的**: 将 v2 的任务定义迁移到 Agent OS

**Step 1: 导出 v2 任务定义**

```bash
psql -d quant_investment -c "SELECT * FROM scheduler_tasks;" -o /tmp/v2_tasks.txt
```

**Step 2: 查看任务内容**

```sql
SELECT id, name, cron_expression, enabled, description 
FROM scheduler_tasks;
```

**Step 3: 在 Agent OS 中手动注册任务**

```bash
# 任务 1
agent-os scheduler register \
  --name "task_name_from_v2" \
  --cron "0 9 * * *" \
  --owner "fin-agent" \
  --command "agent-ts" \
  --description "从 v2 迁移的任务"

# 任务 2
agent-os scheduler register ...

# ... 依此类推（6 个任务）
```

**工期**: 30 分钟

---

### 任务 3: 验证 Notification 配置（可选）

**目的**: 确认 Agent OS 的 notification 配置正确

**Step 1: 查看 v2 配置**

```sql
SELECT * FROM notification_providers;
SELECT * FROM notification_channels;
```

**Step 2: 在 Agent OS 中验证**

```bash
agent-os notify list
```

**Step 3: 如需要，更新 webhook**

```sql
-- Agent OS
UPDATE notification_channels 
SET config = '{"webhook": "https://..."}' 
WHERE code = 'trading';
```

**工期**: 15 分钟

---

## ✅ 简化后的 Phase 1 计划

### 新的时间表

| 任务 | 原计划工期 | 新计划工期 | 节省 |
|---|---|---|---|
| ~~Memory 迁移~~ | 1 小时 | ❌ 跳过 | -1h |
| Decision 迁移 | 30 分钟 | 10 分钟 | -20m |
| Scheduler 迁移 | 1 小时 | 30 分钟 | -30m |
| Notification 验证 | - | 15 分钟 | +15m |
| **总计** | **2.5 小时** | **55 分钟** | **-1.6h** |

---

## 🎯 新的 Phase 1 目标

### 从数据迁移到系统切换

**原目标**（数据为中心）:
- 迁移所有 v2 数据到 Agent OS

**新目标**（功能为中心）:
- ✅ **任务 1.1**: 数据库准备（已完成）
- ✅ **任务 1.2**: Decisions 表验证（10 分钟）
- ✅ **任务 1.3**: Scheduler 任务迁移（30 分钟）
- ✅ **任务 1.4**: Notification 配置验证（15 分钟）
- ✅ **任务 1.5**: agent-ts CLI 集成（2-3 小时）⭐ 最重要
- ✅ **任务 1.6**: 端到端测试（30 分钟）

**新的总工期**: **4 小时**（vs 原计划 6-7 小时）

---

## 📊 为什么 Memory 不需要迁移？

### 原因分析

1. **v2 中不存在 agent_memory 表**
   - Memory 功能可能未在 v2 实现
   - 或者使用了其他存储方式（文件？其他 DB？）

2. **Agent OS 已有完整 Memory 实现**
   - memories 表已创建
   - Memory Service 已实现
   - CLI 命令已完成

3. **从空白开始更干净**
   - 无历史包袱
   - 无数据迁移风险
   - agent-ts 从 Agent OS 开始积累新记忆

**结论**: Memory 从零开始，通过 agent-ts 日常使用自然积累

---

## 🚀 下一步行动（按优先级）

### 立即执行（今天）

**任务 1.2**: Decision 表验证（10 分钟）
```bash
# 1. 检查结构
psql -d quant_investment -c "\d decisions"
psql -d agent_os -c "\d decisions"

# 2. 查看 v2 数据
psql -d quant_investment -c "SELECT * FROM decisions;"

# 3. 如果兼容，迁移
# （我来帮你执行）
```

**任务 1.3**: Scheduler 任务手动迁移（30 分钟）
```bash
# 1. 导出 v2 任务
psql -d quant_investment -c "SELECT id, name, cron_expression, enabled, description FROM scheduler_tasks;"

# 2. 逐个在 Agent OS 注册
# （我来帮你执行）
```

---

### 重点工作（明天/本周）

**任务 1.5**: agent-ts CLI 集成（2-3 小时）⭐
- 这是 Phase 1 的**核心任务**
- agent-ts 从 v2 HTTP API 切换到 Agent OS CLI
- 涉及代码改造，需要专注时间

**任务 1.6**: 端到端测试（30 分钟）
- 验证整个流程打通
- agent-ts → Agent OS → 数据库

---

## 💬 你的决定

**现在有三个选择**：

1. **"立即执行任务 1.2"** → 验证并迁移 Decision 数据（10 分钟）
2. **"立即执行任务 1.3"** → 迁移 Scheduler 任务（30 分钟）
3. **"跳到任务 1.5"** → 直接做 agent-ts CLI 集成（最重要）

**或者**：

4. **"今天就到这"** → 审计工作已完成，明天继续 Phase 1

---

## 📈 今天的成果总结

### 已完成

1. ✅ **Agent OS 审计**（批次 1+2+3）
2. ✅ **问题修复**（9 个问题全部解决）
3. ✅ **技术债清零**
4. ✅ **Memory MoA 设计**（v2，完整方案）
5. ✅ **v2 迁移计划**（完整规划）
6. ✅ **Phase 1 执行计划**（详细步骤）
7. ✅ **迁移范围重新评估**（务实简化）
8. ✅ **任务 1.1 完成**（数据库准备）

### 文档产出（今天）

- 15 份设计文档
- 4 份审计报告
- 3 份执行计划
- **总计**: 22 份高质量文档

---

**告诉我下一步！** 🚀
