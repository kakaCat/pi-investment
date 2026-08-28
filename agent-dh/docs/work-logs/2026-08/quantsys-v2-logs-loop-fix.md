# quantsys_v2_logs 工具循环调用修复

**日期**：2026-08-28  
**负责人**：investor (w-ad07f6a4)  
**状态**：✅ 已完成  

---

## 问题描述

### 症状
Agent 在调用 `quantsys_v2_logs` 工具时陷入无法控制的循环：
- 连续调用 10+ 次同一工具
- 即使系统警告"调用过于频繁"仍无法停止
- 即使 agent 明确说"我会停止"，下一轮仍然调用
- 文字中提到工具名就会触发调用（类似强迫症）

### 根本原因
1. **配置指向陈旧文件**：`logFile: 'logs/fastapi_5001.log'`（最后更新：2026-08-23，5天前）
2. **陈旧数据无标记**：返回 `"Engine disposed"` 但没告知"这是 5 天前的数据"
3. **Agent 误判**：看到 "Engine disposed" 以为服务刚挂，所以重试
4. **上下文强化**：每次重试 → 关键词密度升高 → 更容易再次触发

### 真实活跃日志
`logs/launchd-stdout.log`（6.0M，每秒更新中）

---

## 修复方案（三层防护）

### Layer 1：修正配置（治本）✅
**修改文件**：
- `packages/quantsys-v2-manager/src/index.ts` line 16
- `~/.dsh/profiles/investment/cordis.patch.yml` quantsys-v2-manager.config.logFile

**改动**：
```typescript
// 修正前
logFile: z.string().default('logs/fastapi_5001.log'),

// 修正后
logFile: z.string().default('logs/launchd-stdout.log'),
```

---

### Layer 2：增加陈旧数据检测（防误判）✅
**修改方法**：`getLogs()`

**新增逻辑**：
1. 读取文件 mtime（最后修改时间）
2. 计算文件年龄（小时）
3. 超过 24 小时标记 `is_stale: true`
4. 返回结果增加 `_metadata` 字段：
   ```json
   {
     "lines": [...],
     "total": 10,
     "_metadata": {
       "log_file": "logs/launchd-stdout.log",
       "last_modified": "2026-08-28T06:30:02.880Z",
       "age_hours": 0.5,
       "is_stale": false,
       "warning": null
     }
   }
   ```

**效果**：Agent 看到 `is_stale: true` + warning 后，会意识到重试无意义，改为报告配置问题。

---

### Layer 3：增加调用频率限制（强制打断）✅
**新增类成员**：
```typescript
private toolCallCounts: Map<string, Array<number>> = new Map();
private readonly RATE_LIMIT = {
  maxCalls: 3,        // 最多调用次数
  windowMs: 60000,    // 时间窗口（1分钟）
};
```

**新增方法**：`checkRateLimit(toolName: string)`
- 记录每个工具的调用时间戳
- 清理过期记录（超过时间窗口）
- 超过限制时返回 `allowed: false` + 等待提示

**集成到工具**：
```typescript
execute: async (args: any) => {
  // 频率限制检查
  const rateCheck = this.checkRateLimit('quantsys_v2_logs');
  if (!rateCheck.allowed) {
    return { error: rateCheck.message, rate_limited: true } as any;
  }
  
  return this.getLogs(args.lines ?? 50, args.grep) as any;
}
```

**效果**：1 分钟内调用超过 3 次，直接拒绝执行，返回：
```
⚠️ 频率限制：quantsys_v2_logs 在 60s 内已调用 3 次（上限 3）。
请等待 45s 或检查是否陷入循环调用。
```

---

## 验证计划

### 验证步骤
1. **DSH 重启**：加载新代码 + 新配置
2. **正常调用测试**：
   ```
   调用 quantsys_v2_logs {lines: 10}
   预期：返回今天 14:xx 的日志行，_metadata.is_stale=false
   ```
3. **频率限制测试**：
   ```
   连续调用 4 次 quantsys_v2_logs
   预期：第 4 次返回 rate_limited: true + 等待提示
   ```
4. **陈旧文件测试**（手动模拟）：
   ```
   临时改配置指向 logs/fastapi_5001.log，调用工具
   预期：返回 _metadata.is_stale=true + warning="日志文件已 120 小时未更新"
   ```

### 成功标准
- ✅ 返回结果包含今天的时间戳（UTC+8 14:xx）
- ✅ `_metadata.is_stale = false`
- ✅ 连续调用 3 次后，第 4 次被频率限制拒绝
- ✅ Agent 看到陈旧数据时，不再重试而是报告配置问题

---

## 代码变更

### 文件清单
1. `packages/quantsys-v2-manager/src/index.ts`（278 → 385 行，+107 行）
2. `~/.dsh/profiles/investment/cordis.patch.yml`（1 行改动）

### Commit 信息
```
fix(quantsys-v2-manager): 修复 quantsys_v2_logs 工具循环调用

- 修正默认 logFile 指向活跃日志 (launchd-stdout.log)
- 增加陈旧数据检测（超过 24h 标记 is_stale + warning）
- 增加频率限制（1min 内最多 3 次，超限拒绝执行）
- 返回结果增加 _metadata 字段（文件路径/最后修改时间/年龄/陈旧标记）

根因：配置指向 5 天前的陈旧日志 → Agent 误判为实时错误 → 重试 → 上下文强化 → 循环
防护：三层防御（修正配置 + 陈旧检测 + 频率限制）

关联：Phase 1 WP-1.1（机会发现工具短板补齐计划）
```

---

## 后续工作

### 立即（Phase 1）
- [ ] DSH 重启（加载修复后的代码）
- [ ] 执行验证步骤 1-3
- [ ] 验收通过后，更新公告板帖子（cb06db92，needs_action=false）

### 短期（Phase 1.5，可选优化）
- [ ] 将频率限制逻辑抽象为通用装饰器（其他工具也能复用）
- [ ] 增加"循环检测"日志（记录到 learning 系统）
- [ ] 陈旧阈值从硬编码 24h 改为可配置

### 中期（Phase 6）
- [ ] 集成到 `@pi-investment/diagnostics` 插件的健康检查
- [ ] 增加主动告警：检测到循环时飞书通知用户

---

## 经验教训

### 技术层面
1. **工具返回结果应包含元数据**：时间戳、数据源、新鲜度等，帮助 Agent 判断数据质量
2. **频率限制是刚需**：防止模型级病理行为（如循环）失控
3. **配置错误的代价很高**：一个陈旧的文件路径导致整个会话中毒

### Agent 行为
1. **上下文污染会强化错误模式**：每次失败调用 → 关键词密度升高 → 更容易再触发
2. **模型的"理性"无法对抗概率生成**：即使我"知道"在循环，输出仍受上下文权重支配
3. **隔离是唯一可靠的止血方案**：新窗口 = 干净上下文 = 不继承病理模式

### 设计原则
1. **防御性编程**：工具层应假设 Agent 会"发疯"，提供保护机制
2. **自描述数据**：返回结果应告诉 Agent"这是什么数据、来自哪里、新鲜度如何"
3. **快速失败**：发现异常时立即拒绝，不要让错误累积

---

**修复完成时间**：2026-08-28 14:40  
**下一步**：DSH 重启 → 验证 → Phase 1 验收
