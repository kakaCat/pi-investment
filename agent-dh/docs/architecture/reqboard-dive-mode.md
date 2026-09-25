# Reqboard Dive 模式架构设计

**需求**: REQ-260925212722-96e7  
**版本**: 1.0  
**更新**: 2026-09-25

## 概述

Dive 模式是项目看板（reqboard）的自动流程控制机制，实现需求从立项到归档的自动化推进，减少人工干预，提高执行效率。

## 核心概念

### Dive 状态机

需求对象新增 `dive` 字段：

```typescript
interface RequirementDive {
  activation: 'armed' | 'disarmed'  // 自动流程开关
  phase: 'idle' | 'active' | 'paused'  // 执行阶段
  roundsInStage: number  // 当前阶段的续跑回合数
  pausedReason?: string  // 暂停原因
}
```

### 阶段配置

每个需求状态对应一个阶段配置（`StageConfig`）：

- `maxRounds`: 最大续跑回合数
- `requiresHuman`: 是否需要人工门禁
- `autoAdvance`: 是否自动推进到下一阶段

## 架构组件

### 1. RTM 门禁系统

**位置**: `packages/tools/reqboard/src/rtm/`

三个核心门禁：

#### 设计门禁 (Design Gate)
- **触发**: design → decomposing
- **检查**: 所有 FR 的 `design_refs` 是否已填写
- **实现**: `designGateCheck()`

#### 拆分门禁 (Task Coverage Gate)
- **触发**: decomposing → implementing
- **检查**: 所有 FR 的 `task_refs` 是否已覆盖
- **实现**: `taskCoverageGateCheck()`

#### 验收门禁 (Acceptance Gate)
- **触发**: accepting → archived
- **检查**: 所有 FR 的 `acceptance_status` 是否为 `passed`
- **实现**: `acceptanceGateCheck()`

### 2. DiveManager

**位置**: `packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts`

**职责**:
- 监听回合结束事件
- 检查需求的 dive 状态
- 自动调用 agent 续跑
- 管理回合数和暂停逻辑

**关键方法**:
- `checkAndContinue(sessionId)`: 检查并续跑
- `shouldContinue(req)`: 判断是否应该续跑
- `incrementRounds(req)`: 增加回合数

### 3. Armed 检查

在三个关键工具中添加 armed 检查，防止手动干预：

#### Decompose
**位置**: `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`
- **检查**: `dive?.activation === 'armed'`
- **拒绝**: 不允许手动拆分

#### MoveRequirement
**位置**: `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
- **检查**: `to === 'implementing' && dive?.activation === 'armed'`
- **拒绝**: 不允许手动推进到 implementing

#### MoveTask
**位置**: `packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`
- **检查**: `dive?.activation === 'armed' && task.parentId`
- **拒绝**: 不允许手动推进子任务

### 4. 解锁工具

**工具**: `reqboard_clear_pause`  
**位置**: `packages/web/dsh-pmboard/src/application/use-cases/ClearPause.ts`

**功能**:
- 设置 `dive.activation = 'disarmed'`
- 清除 `pausedReason`
- 记录解锁日志

## 数据流

```
用户创建需求
    ↓
设置 dive.activation = 'armed'
    ↓
自动推进流程（DiveManager）
    ↓
遇到门禁 → 检查 → 通过/阻塞
    ↓
达到回合数限制 → 暂停 (pausedReason)
    ↓
需要人工干预 → reqboard_clear_pause
```

## 测试覆盖

### 单元测试
- 设计门禁: `tests/rtm/design-gate.test.ts` (3个用例)
- 拆分门禁: `tests/rtm/task-coverage-gate.test.ts` (3个用例)
- 验收门禁: `tests/rtm/acceptance-gate.test.ts` (3个用例)

### E2E 测试
- 完整流程: `tests/e2e/dive-full-flow.test.ts` (11个场景)

## 已知限制

1. **DiveManager 依赖 agent 服务**: 需要 agents 服务可用才能自动续跑
2. **回合数限制**: 防止无限循环，但可能需要人工介入
3. **门禁规则固定**: 当前门禁规则是硬编码的，未来可能需要配置化

## 未来优化

1. **动态阶段配置**: 支持每个需求类型配置不同的阶段参数
2. **门禁规则可配置**: 允许自定义门禁检查逻辑
3. **更智能的暂停恢复**: 根据暂停原因自动选择恢复策略
4. **性能优化**: 批量处理多个需求的 dive 检查

## 参考

- 需求文档: `docs/requirements/REQ-260925212722-96e7/`
- 拆分计划: `docs/requirements/REQ-260925212722-96e7/decomposition.md`
