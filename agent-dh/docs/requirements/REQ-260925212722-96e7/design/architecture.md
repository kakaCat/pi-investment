# 架构设计

> REQ-260925212722-96e7: REQ 流水线 Dive 模式重构

## 设计决策：独立实现 vs 复用 DSH Goal «serves: FR-1, FR-2»

**决策：选择独立实现（选项 A）**

### 理由 «serves: FR-1, FR-2»

1. **需求流水线有自己的业务逻辑**
   - 多阶段流程（brainstorming → design → ... → accepting）
   - 每个阶段有不同的验收标准
   - 阶段间有门禁检查
   - 需要精确控制每个阶段的行为

2. **不耦合 DSH Goal 实现**
   - Goal 是 DSH 框架的通用机制，适合单一目标场景
   - 需求流水线是特定业务逻辑，有自己的状态模型
   - 独立实现更清晰，便于针对需求流水线优化

3. **状态存储不同**
   - Goal 状态存储在 agents.json（session 级别）
   - 需求状态存储在数据库 requirements 表（持久化）
   - 需求需要跨 session 持久化

### 借鉴 DSH Goal 的设计模式 «serves: FR-1, FR-2»

虽然独立实现，但借鉴 Goal 的核心思路：
- ✅ 状态机模式（phase + activation）
- ✅ 回合结束时检查并续跑的机制
- ✅ armed/disarmed 锁定模式
- ✅ 回合限制和失败处理

## 总体架构 «serves: FR-1, FR-2, FR-3»

### 当前架构问题 «serves: FR-3»

```
用户批准计划
    ↓
confirm-settle.ts 回调
    ↓
executeDecompose(deps, args, exec) ← 需要 live driver
    ↓
❌ 失败：agent 回合已结束，无 currentInitiator()
```

### 目标架构 «serves: FR-1, FR-2, FR-3»

```
用户批准计划
    ↓
confirm-settle.ts 回调
    ↓
deps.jobs.start() ← 后台 job，不需要 driver
    ↓
✅ 自动拆分成功，设置 autoRun=true
    ↓
DSH 回合结束检查
    ↓
ReqboardDiveManager.checkAndContinue()
    ↓
发起新回合（followup）
```

### 核心组件 «serves: FR-1, FR-2, FR-8»

**1. Dive 状态机（Requirement.dive）**
- 管理需求的自动续跑状态
- 控制 armed/disarmed 锁定
- 记录阶段进度和失败原因

**2. Dive 管理器（ReqboardDiveManager）**
- 在 agent 回合结束时检查 dive 状态
- 决定是否发起新回合
- 集成到 pmboard 插件生命周期

**3. RTM 门禁系统**
- 设计门禁：design → decomposing
- 拆分门禁：decomposing → implementing
- 验收门禁：accepting → archived

**4. armed 锁机制**
- reqboard_decompose 检查 armed
- reqboard_move 检查 armed
- reqboard_task_move 检查 armed

## 模块划分 «serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7»

```
packages/web/dsh-pmboard/src/
├── shared/
│   └── protocol.ts                    # RequirementDive 接口定义
├── application/
│   ├── dive/
│   │   ├── ReqboardDiveManager.ts    # Dive 续跑管理器
│   │   └── stage-configs.ts          # 阶段配置（STAGE_CONFIGS）
│   ├── gate/
│   │   ├── design-gate.ts            # 设计门禁
│   │   ├── task-coverage-gate.ts     # 拆分门禁
│   │   └── acceptance-gate.ts        # 验收门禁
│   ├── internal/
│   │   └── confirm-settle.ts         # 修改：改用 deps.jobs.start
│   └── use-cases/
│       ├── Decompose.ts              # 修改：检查 armed
│       ├── MoveRequirement.ts        # 修改：检查 armed
│       └── MoveTask.ts               # 修改：检查 armed
└── index.ts                          # 修改：注册 ReqboardDiveManager
```

## 依赖关系 «serves: FR-2, FR-3»

### 外部依赖 «serves: FR-2»

- **DSH Framework**
  - `ctx.agents` - 获取 agent 实例
  - `agent.followup()` - 发起新回合
  - `deps.jobs.start()` - 启动后台任务

### 内部依赖 «serves: FR-2»

- **ReqboardDiveManager** 依赖：
  - `ctx.agents` - 获取 agent 列表
  - `reqboard` service - 查询需求状态

- **confirm-settle.ts** 依赖：
  - `deps.jobs` - 启动后台拆分任务
  - 不再依赖 `exec` (live driver)

- **门禁系统** 依赖：
  - RTM 数据（需求文档解析结果）
  - Requirement 状态

## 数据流 «serves: FR-1, FR-2, FR-3»

### Dive 续跑流程 «serves: FR-2»

```
1. 用户批准拆分计划
   ↓
2. confirm-settle.ts 调用 deps.jobs.start()
   ↓
3. 后台 job 执行拆分
   ↓
4. 设置 requirement.dive.activation = 'armed'
   ↓
5. agent 回合结束
   ↓
6. ReqboardDiveManager.checkAndContinue()
   ↓
7. 检查 dive.activation === 'armed' && dive.phase === 'active'
   ↓
8. agent.followup("继续执行当前阶段任务")
   ↓
9. 新回合开始，agent 自动继续工作
```

### RTM 门禁流程 «serves: FR-4, FR-5, FR-6»

```
1. agent 调用 reqboard_move(to='decomposing')
   ↓
2. 系统调用 designGateCheck(requirement)
   ↓
3. 检查所有 FR 是否都有 design_refs
   ↓
4. 有 FR 未覆盖 → 返回 { passed: false, gaps: [...] }
   ↓
5. 推进被阻塞，返回错误给 agent
```

### armed 锁流程 «serves: FR-7»

```
1. agent 调用 reqboard_decompose()
   ↓
2. 检查 requirement.dive?.activation === 'armed'
   ↓
3. 是 → 抛出错误："dive 自动流程已启用，不允许手动拆分"
   ↓
4. agent 被阻止手动操作
```

## 向后兼容 «serves: FR-1, FR-7»

### 老需求 «serves: FR-1»

- `requirement.dive === undefined` → 手动模式
- 所有工具行为保持不变
- 不检查 armed 锁

### 新需求 «serves: FR-1, FR-2»

- 创建时可选启用 dive 模式
- `requirement.dive = { activation: 'armed', phase: 'active', ... }`
- 启用 armed 锁和自动续跑

## 非功能需求 «serves: FR-2, FR-8»

### 性能 «serves: FR-2»

- Dive 续跑检查延迟 < 1s
- RTM 门禁检查延迟 < 2s
- 不影响现有需求的性能

### 可观测性 «serves: FR-2»

- Dive 状态变化写入需求评论
- 门禁检查结果可追溯
- armed 锁定/解锁有日志

### 可维护性 «serves: FR-1, FR-2»

- 阶段配置集中管理（STAGE_CONFIGS）
- 门禁逻辑独立模块
- 清晰的错误码体系