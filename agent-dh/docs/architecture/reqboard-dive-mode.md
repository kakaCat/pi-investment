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

## 续跑驱动器对齐 DSH Goal round driver（2026-09-26，REQ-260926215013-1568）

Dive 的两半驱动器已按 `@deepseek-ai/dsh-goal-round-driver` 的机制重写（**照其形自实现，不引该依赖**）：

- **驱动点 = 整 agent 空闲**：续跑只在 `agent/status === 'idle'`、无竞争输入、绑定需求 `armed + active` 时起轮；
  `reqboard/requirement-moved` 只置「待检查」标志并请求一次驱动，**不再直接投递**（旧实现会打断正在跑的回合）。
- **回合号 = reservation → admission**：起轮时预留 `round = roundsInStage + 1` 并登记 `attempt`
  （含 messageId / content / source）；只有该消息**真正进入 history**（`user/message` 身份匹配）才把 `roundsInStage` 落库。
  被 reject / discarded / cancelled / stale 的预留**不计数**，下次仍用同一个 round 号。
- **回合上限 = 终态**：达到 `stage-configs.ts` 的 `maxRounds` 时写 `dive.phase='paused'` +
  `pausedReason='round-limit'`（含上限值与阶段）+ 一条台账 comment + 一次 warn——不再「刷一行日志就静默停跑」。
- **五条纪律**：`agent/pre-step` 前后各校验一次（不成立即 reject，并把同批其它已认领消息按原序放回）；
  `agent/inbox/inserted` 检测竞争输入 → 让位到下次空闲；排队前 `await` 台账写队列排空（耐久检查点）；
  每 agent 的驱动经 `ctx.agents.withoutInitiator()` 串行且合并触发；teardown 先关准入 → 解除武装 →
  以 `parent` 取消在飞回合 → 等静默（fail-closed）。
- **回合消息来源标识**：消息带 `source:{kind:'dive',requirementId,revision,round}`，内容不变量逐字比对，
  不一致者在 pre-step 被拒并留痕（防旧 revision 混入）。

**组件**：`application/dive/round-state.ts`（纯契约/判定）、`round-driver.ts`（状态机）、
`round-subscriptions.ts`（七路事件接线）、`ReqboardDiveManager`（订阅持有者 + 端口提供者）、
`session-driver.ts`（采集/簿记半，可选组合 round 半，缺省行为不变）。

**运行注意**：插件运行时加载 `packages/web/dsh-pmboard/dist/index.mjs`，改动须 `pnpm build` + 重启才生效。

## 参考

- 需求文档: `docs/requirements/REQ-260925212722-96e7/`
- 拆分计划: `docs/requirements/REQ-260925212722-96e7/decomposition.md`
