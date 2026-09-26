# 优化：移除 deps.jobs 依赖，启用 Dive 事件驱动续跑

## 问题背景

### 旧架构问题
```
批准拆分计划
    ↓
confirm-settle: await deps.jobs.start(...)
    ↓
❌ deps.jobs 未注入 → undefined
    ↓
错误：Cannot read properties of undefined (reading 'start')
    ↓
需求卡在 decomposing 状态
```

**根本原因**：
1. `deps.jobs.start()` 是为了解决 "Agent 回合已结束" 的问题
2. 但 Dive 自动续跑本身就有 Agent 上下文
3. `deps.jobs` 成为多余的中间层
4. 且 `deps.jobs` 未注入，导致失败

## 优化方案

### 新架构（事件驱动）
```
批准拆分计划
    ↓
confirm-settle: 只推进状态
    ↓
状态推进：decomposing → implementing
    ↓
发出事件：'requirement-moved'
    ↓
【毫秒级响应】
    ↓
Dive 管理器监听到事件
    ↓
触发 agent.followup(...)
    ↓
Agent 新回合启动
    ↓
检测到：implementing + tasks.length=0
    ↓
自动执行 reqboard_decompose
    ↓
创建任务 → 开始执行
```

## 修改的文件

### 1. confirm-settle.ts
**变更**：移除整个 `deps.jobs.start()` 逻辑块（~40行）

**前**：
```typescript
if (deps.jobs === undefined || !deps.jobs.available()) {
  // 错误处理...
} else {
  const jobId = await deps.jobs.start({
    kind: 'reqboard_decompose',
    // ...
  })
}
```

**后**：
```typescript
// 优化：移除 deps.jobs 依赖，改为 Dive 续跑模式（事件驱动，毫秒级响应）
// 批准计划后只推进状态，Dive 管理器监听事件立即触发续跑
const createdCount = 0 // 任务将由 Dive 续跑时创建
```

### 2. ReqboardDiveManager.ts
**变更**：完全重写，添加事件驱动续跑机制（~200行）

**核心改动**：
1. `setupEventListeners()` - 监听 `'reqboard/requirement-moved'` 事件
2. `shouldContinue()` - 检查是否应该续跑
3. `triggerContinuation()` - 触发 agent.followup()
4. 修复 `getActiveRequirement()` - 从 reqboard.store 获取需求
5. 修复 `incrementRound()` - 更新回合数

**关键逻辑**：
```typescript
ctx.on('reqboard/requirement-moved', async (data) => {
  const req = await this.getActiveRequirement(data.requirementId)
  if (this.shouldContinue(req)) {
    await this.triggerContinuation(req)
  }
})
```

### 3. index.ts
**变更**：添加 store 订阅桥接（~20行）

**功能**：将 store 内部订阅机制桥接到 Cordis 事件系统

```typescript
store.subscribe((change) => {
  if (change.kind === 'requirement-moved' && change.requirements.length > 0) {
    for (const req of change.requirements) {
      ctx.emit('reqboard/requirement-moved', {
        requirementId: req.id,
        from: prevStatus,
        to: req.status,
      })
    }
  }
})
```

## 优势对比

| 维度 | 旧方案（deps.jobs） | 新方案（Dive 事件驱动） |
|------|---------------------|-------------------------|
| 依赖复杂度 | ❌ 需要 deps.jobs 端口 | ✅ 无额外依赖 |
| 响应速度 | ✅ 立即执行 | ✅ 毫秒级（事件驱动） |
| 架构简洁性 | ❌ 多一层抽象 | ✅ 直接、清晰 |
| 调试难度 | ❌ 异步难追踪 | ✅ 同步易调试 |
| 错误处理 | ❌ 需要空值检查 | ✅ 统一处理 |
| 失败风险 | ❌ deps.jobs 未注入即失败 | ✅ Agent 上下文可靠 |

## 验收标准

### 功能验收
- [x] 编译通过
- [ ] 批准拆分计划后，状态正确推进
- [ ] Dive 管理器监听到事件并触发续跑
- [ ] Agent 续跑时自动检测并执行拆分
- [ ] 任务创建成功，autoRun=true
- [ ] 自动开始执行第一个任务

### 性能验收
- [ ] 批准计划后 < 1秒触发续跑
- [ ] 无 deps.jobs 依赖错误
- [ ] 日志显示完整的事件驱动流程

### 回归验收
- [ ] 手动模式不受影响
- [ ] 非 Dive 需求不受影响
- [ ] 其他阶段推进正常

## 测试方法

```bash
# 1. 重启 DSH
# 2. 创建新需求（Dive armed 模式）
# 3. 提交需求文档 → 提交设计文档 → 提交拆分计划
# 4. 批准拆分计划
# 5. 观察日志：
#    - "Detected requirement-moved"
#    - "Triggering Dive continuation"
#    - "Dive continuation triggered"
# 6. 确认任务已创建且开始执行
```

## 回滚方案

如果出现问题，回滚步骤：
1. 恢复 confirm-settle.ts 的 deps.jobs.start() 逻辑
2. 恢复旧的 ReqboardDiveManager.ts
3. 移除 index.ts 的订阅桥接

## 后续优化

1. **提示词增强**：在 implementing 提示词中明确说明拆分检测逻辑
2. **监控指标**：添加 Dive 续跑触发次数、延迟等指标
3. **失败重试**：Dive 续跑失败时的自动重试机制

## 相关需求

- REQ-260925212722-96e7：Dive 模式重构（引入 deps.jobs）
- 本次优化：移除 deps.jobs，启用真正的 Dive 事件驱动续跑
