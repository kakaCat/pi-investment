
# 拆分逻辑分析报告

## 当前拆分流程

### 1. 拆分入口 (reqboard_decompose)
- **工具**: `src/tools/DecomposeTool/DecomposeTool.ts`
- **用例**: `src/application/use-cases/Decompose.ts`

### 2. 核心逻辑 (executeDecompose)

#### 2.1 前置检查（会阻碍流程的错误）

**A. 窗口绑定检查**
- ❌ 本窗口没有绑定需求 → REQBOARD_NO_BOUND_REQ
- ❌ 需求不属于本窗口 → REQBOARD_NOT_BOUND_TO_WINDOW

**B. Dive 模式检查**
- ❌ Dive 模式已启用 (armed) → REQBOARD_DIVE_ARMED
  - 需要先调用 reqboard_clear_pause() 解除锁定

**C. 状态检查**
- ❌ 需求还在 draft 态 → REQBOARD_BAD_STATUS
- ❌ 需求已完成/归档/取消 → REQBOARD_BAD_STATUS

**D. 幂等守卫（防止重复拆分）**
- ❌ 状态已越过拆分（implementing/accepting）且已有任务 → 拒绝
- ✅ 在 decomposing 状态下可以拆分（2026-09-17 修正）

**E. 计划批准闸门（硬门槛）**
- ❌ 计划未批准 → REQBOARD_PLAN_NOT_APPROVED
  - 必须先 `reqboard_submit(kind=plan)` 提交计划
  - 然后人工批准（看板或弹框）

**F. 任务表校验**
两条路径:
- **路径 A (创作型)**: 计划不含任务表 → 必须显式传 tasks 参数
  - ❌ tasks 为空或未传 → REQBOARD_TASKS_REQUIRED
  - tasks 必须含 `implementation` 和可证伪的 `acceptance`
  
- **路径 B (计划携带)**: 计划已含任务表
  - ❌ 显式传 tasks 但 key 集合不一致 → REQBOARD_PLAN_MISMATCH
  - ⚠️ 薄卡检测: implementation 为空 → 返回 thin_cards 警告（不硬拦）

**G. 冲突检测**
- ❌ 互无依赖的任务声明了同一文件 → REQBOARD_FILE_CONFLICT
  - 并行执行会互相覆盖

**H. 覆盖门禁（FR 接收检查）**
- ❌ 需求中的 FR 编号未被任何任务接收 → 拒绝
  - 任务必须用 `requirement_refs` 声明接收哪些 FR

#### 2.2 落库流程 (landPlanTasks)

**步骤 1: 生成任务记录**
```
for each task in draft:
  - 生成唯一 id (t-xxxxxx)
  - 解析 dependsOn (key → id)
  - 创建 TaskRecord:
    - id, title, description
    - phase (implement/test/doc/review/ui/analysis/merge)
    - side (backend/frontend/fullstack/doc)
    - acceptance, implementation
    - requirementRefs (FR-1, FR-2, ...)
    - cardDoc 路径
```

**步骤 2: DAG 环检测**
```
assertDagAcyclic([...existing, ...newTasks])
```
- ❌ 依赖图有环 → 拒绝

**步骤 3: 写入队列文件**
```
queue.json 位置: docs/requirements/<REQ>/queue.json
```
- 幂等: 已存在的 id 跳过
- 全部已存在 → 不写盘 (mtime 不变)

**步骤 4: 生成产物**
- 任务卡文档: `docs/requirements/<REQ>/tasks/<task-id>.md`
- RTM 覆盖表
- 登记 decomposition 产物

#### 2.3 返回信息

```typescript
{
  success: true,
  requirement_id: "REQ-xxx",
  requirement_status: "implementing",
  queue_file: "docs/requirements/REQ-xxx/queue.json",
  tasks_created: 5,  // 本次新增数量
  created: [
    { key: "t1", id: "t-abc123", title: "...", depends_on: [] }
  ],
  task_coverage: [...],  // RTM 覆盖度
  coverage_check: {
    unreceived_clauses: ["FR-3"],  // 未被接收的 FR
    coverage_rate: 85  // 覆盖率 %
  },
  thin_cards: ["t1 xxx"],  // 薄卡警告
  warning: "...",
  note: "..."
}
```

### 3. queue.json 结构

```json
{
  "version": 1,
  "requirement_id": "REQ-xxx",
  "schemaVersion": 9,
  "generated_at": "2026-09-27...",
  "tasks": [
    {
      "id": "t-abc123",
      "requirementId": "REQ-xxx",
      "title": "任务标题",
      "description": "任务描述",
      "phase": "implement",
      "side": "backend",
      "dependsOn": ["t-def456"],  // 依赖的任务 id
      "scope": { "apis": [], "tables": [], "files": [] },
      "acceptance": "可证伪的验收标准",
      "implementation": "实施方案",
      "status": "todo",
      "executions": [],
      ...
    }
  ],
  "layers": [...],  // DAG 分层（用于渲染）
  "edges": [...]    // DAG 边线（用于渲染）
}
```

### 4. DAG 可视化关键字段

**用于渲染的字段:**
- `tasks[].id` - 节点 id
- `tasks[].title` - 节点标题
- `tasks[].phase` - 决定卡片类型徽标颜色
- `tasks[].side` - 决定端侧徽标颜色
- `tasks[].status` - 决定卡片底色
- `tasks[].dependsOn` - 依赖关系（边线）
- `layers` - 节点分层（用于布局）
- `edges` - 边线列表（from → to）

## 可能阻碍流程的错误

### 错误类型 1: 计划结构错误
- ❌ 任务 key 重复
- ❌ dependsOn 引用不存在的 key
- ❌ 依赖形成环

### 错误类型 2: FR 覆盖不完整
- ❌ requirement.md 中定义的 FR-N 没有被任何任务接收
- 需要在 tasks 中添加 `requirement_refs: ["FR-1", "FR-2"]`

### 错误类型 3: 文件冲突
- ❌ 两个无依赖关系的任务声明修改同一文件
- 需要添加依赖或重划范围

### 错误类型 4: 薄卡（警告级）
- ⚠️ implementation 字段为空
- 不阻止拆分，但会返回警告

### 错误类型 5: 状态异常
- ❌ 在错误的状态下调用 decompose
- ❌ 计划未批准就尝试拆分

## 当前需求状态

- **状态**: brainstorming
- **下一步**: 需要先进入 design 阶段，写设计文档
- **拆分时机**: design 确认后进入 decomposing，才能写拆分计划并拆分

## 建议

1. 当前需求还未到拆分阶段，无需担心拆分逻辑
2. 拆分逻辑有完善的错误检查，会在问题发生前拦截
3. 关键是拆分计划要写好:
   - 任务依赖要正确
   - FR 覆盖要完整
   - 避免文件冲突
