---
id: rtm-yaml-usage
title: RTM YAML 追溯基础设施使用指南
summary: 需求追溯的预构建索引：7 个 YAML 文件长什么样、在哪 7 个时刻自动更新、Dive 模式怎么 2ms 读它做决策、节点输入包怎么注入与压缩。
type: guide
status: living
updated: 2026-09-26
owners: [session-c5ea210f]
tags: [rtm, reqboard, traceability, dive, guide]
---

# RTM YAML 追溯基础设施使用指南

> **这一页解决什么**：需求流水线的**追溯关系**过去要靠实时解析 `requirement.md` + `design/*.md` +
> 台账才能拼出来（~500ms），Dive 模式跑不动。现在改成**预构建索引**：需求流程走到哪一步，
> 就把那一层的追溯关系写进 `docs/requirements/<REQ>/rtm-*.yml`，读取只要 ~1ms/文件。
>
> **与另一份 RTM 文档的区别**：[RTM 使用指南](rtm-user-guide.md) 讲的是台账内的
> `task_coverage` / `acceptance_tracking`（覆盖度与验收追踪，存在 dsh-reqboard.json 里）；
> 本页讲的是**独立的 RTM YAML 文件**（追溯链快照，存在需求目录里）。两者互补，不重复。
>
> **代码在哪**：`agent-dh/packages/tools/reqboard/src/rtm/`（生成引擎，纯函数 + 文件 IO，可脱离运行实例单测）
> 与 `agent-dh/packages/tools/reqboard/src/stage-overview/`（读取与装配）。
> 触发点接线在 `dsh-pmboard/src/application/internal/rtm-yaml.ts`。

## 1. 七个文件长什么样

每个需求一个目录，RTM 文件就放在需求目录里：

```
docs/requirements/REQ-xxxxxx/
├── rtm-lifecycle.yml          # 全局：当前阶段 + 七个阶段的状态/时间/已确认产物
├── rtm-brainstorming.yml      # 需求分析：提取到的 FR 列表 + 需求文档确认态
├── rtm-design.yml             # 设计：设计章节 + fr_to_design 映射 + 设计覆盖度
├── rtm-decomposing.yml        # 拆分：任务列表 + design_to_tasks / fr_to_tasks + 实施覆盖度
├── rtm-implementing.yml       # 实施汇总：任务统计（轻量，Dive 只读这个）
├── rtm-implementing/          # 实施详情：每个任务一个文件，含 workflow 子阶段执行链
│   ├── t-8c8edc.yml
│   └── t-e57e00.yml
└── rtm-accepting.yml          # 验收：测试用例 + task_to_tests 映射 + 测试覆盖度
```

**为什么 implementing 要拆成「汇总 + 每个任务一个文件」**：汇总文件只放统计和任务 id/状态
（~50 行），Dive 决策读它；单个任务详情（含 `workflow` 子阶段）独立成 ~30 行文件，
更新时只写变化的那一份——既快，也让多个任务并发更新落在不同文件上。

每个文件结构一致：`metadata`（含 `version` / `last_updated`）+ 节点专属的
`inputs` / `outputs` / `traceability` / `coverage`。**每次写入 `metadata.version` 自增 1**，
可用于判断下游是否过期。

```yaml
# rtm-implementing.yml（汇总，轻量）
metadata:
  stage: implementing
  requirement_id: REQ-260926140539-457b
  generated_at: '2026-09-26T10:00:00.000Z'
  last_updated: '2026-09-26T10:31:00.000Z'
  version: 7
  detail_dir: rtm-implementing/
  detail_count: 20
status:
  tasks_total: 20
  tasks_done: 3
  tasks_in_progress: 1
  tasks_todo: 16
tasks:
  - { id: t-8c8edc, status: done }
  - { id: t-e57e00, status: in_progress }
```

## 2. 七个触发点：什么时候自动更新

触发点都挂在**业务动作之后**，而不是让人手动生成；生成失败**不打断主流程**（FR-9），
只记 warning 并结构化返回。代码入口是 `runRTMTrigger(generator, trigger, reqId, payload)`。

| # | 业务动作 | 触发点 key | 更新/生成的文件 |
|---|---------|-----------|----------------|
| 1 | 立项 `reqboard_create` | `create` | rtm-lifecycle.yml（骨架，current_stage=draft） |
| 2 | 提交需求文档 `reqboard_submit(kind=requirement)` | `submit:requirement` | rtm-brainstorming.yml、rtm-lifecycle.yml |
| 3 | 确认需求产物 `reqboard_ask_confirm` / 看板确认 | `confirm:artifact` | rtm-brainstorming.yml（落章）、rtm-design.yml、rtm-lifecycle.yml |
| 4 | 提交设计文档 `reqboard_submit(kind=design)` | `submit:design` | rtm-design.yml、rtm-lifecycle.yml |
| 5 | 批准拆分计划 `reqboard_ask_confirm(target=plan)` / 看板批准 | `confirm:plan` | rtm-decomposing.yml、rtm-implementing.yml + 任务详情目录、rtm-lifecycle.yml |
| 6 | 任务状态变更 / 任务汇报 | `task:status` / `task:report` | rtm-implementing.yml + 该任务的 rtm-implementing/t-xxx.yml |
| 7 | 提交验收材料 `reqboard_submit(kind=verification)` | `submit:verification` | rtm-accepting.yml、rtm-lifecycle.yml |

**任务状态以台账为唯一事实源**：`task:status` 没显式给状态时，从台账读任务当前状态再落 RTM——
RTM 永远不反过来写台账。

```ts
import { RTMGenerator, runRTMTrigger } from '@pi-investment/reqboard'

const generator = new RTMGenerator({
  workspaceRoot: '/path/to/agent-dh',
  ledger: { requirement: id => /* 台账投影 */, tasksOf: id => /* ... */ },
  generatedBy: 'my-caller',
})

// 提交需求文档之后
const result = runRTMTrigger(generator, 'submit:requirement', 'REQ-260926140539-457b')
if (!result.ok) console.warn('RTM 没更新成功（不影响主流程）：', result.error)
```

## 3. Dive 模式怎么读它做决策

Dive 决策只需要**两个文件**：全局状态（下一步该做什么）+ 当前节点的覆盖度（能不能推进）。

### 示例 1：读两个文件，判断设计节点能不能进拆分

```ts
import { readLifecycleRTM, readDesignRTM } from '@pi-investment/reqboard/stage-overview/rtm-reader'

const lifecycle = readLifecycleRTM(workspaceRoot, reqId)   // ~1ms
const design = readDesignRTM(workspaceRoot, reqId)         // ~1ms

if (design === null) {
  // RTM 缺失 → 降级：实时重建（FR-9）
} else if (design.coverage.design.rate === 100) {
  console.log('所有 FR 都有设计，可以准备拆分')
} else {
  console.log(`还有 ${design.coverage.design.uncovered.length} 个 FR 缺少设计：`,
    design.coverage.design.uncovered)
}
console.log('当前阶段：', lifecycle?.lifecycle.current_stage)
```

### 示例 2：实施节点——任务做完没有、测试够不够

```ts
import { readStageRTM } from '@pi-investment/reqboard/stage-overview/rtm-reader'

const impl = readStageRTM<RTMImplementing>(workspaceRoot, reqId, 'implementing')
if (impl !== null && impl.status.tasks_done === impl.status.tasks_total) {
  const accepting = readStageRTM<RTMAccepting>(workspaceRoot, reqId, 'accepting')
  const rate = accepting?.coverage.testing.rate ?? 0
  console.log(rate >= 80 ? '任务完成且测试充分，可以验收' : `测试覆盖度只有 ${rate}%，需补测试`)
}
```

### 示例 3：取一条 FR 的完整追溯链（会话节点「追溯」页同款）

```ts
import { assembleStageOverviewRTM } from '@pi-investment/reqboard/stage-overview/assembler'
import { buildTraceabilityChain } from '@pi-investment/reqboard'

// 装配追溯 + 覆盖度（RTM 缺失且给了 regenerator 时自动实时重建）
const { traceability, coverage } = assembleStageOverviewRTM({
  workspaceRoot, reqId, regenerator: generator,
})

const chain = buildTraceabilityChain('FR-1', traceability)
// { fr: 'FR-1', designs: ['design/architecture.md#1.1'],
//   tasks: ['t-0001', 't-0004'], tests: ['TC-1'] }
console.log(chain, coverage.design?.rate, coverage.implementation?.rate, coverage.testing?.rate)
```

### 示例 4：性能基线（t19 实测口径）

```ts
import { readRTM } from '@pi-investment/reqboard'
readRTM(lifecyclePath); readRTM(implPath)          // 预热
const t0 = performance.now()
readRTM(lifecyclePath); readRTM(implPath)          // 决策所需的两个文件
console.log('Dive 决策读取耗时', performance.now() - t0, 'ms')  // 目标 < 5ms（原 ~500ms）
```

## 4. 节点输入包怎么注入

节点输入包**不需要自己拼**：`assembleStageOverviewRTM()` 返回的
`{ traceability, coverage }` 是**加性块**，直接展开进既有响应即可。
dsh-pmboard 的节点查询把这个块透出给会话面板，Dive 注入时按当前阶段取对应字段：

| 节点 | 注入什么 |
|------|---------|
| brainstorming | `outputs.requirements`（FR 列表） |
| design | FR 列表 + `fr_to_design` + `coverage.design` |
| decomposing | 设计章节 + `design_to_tasks` + `coverage.implementation` |
| implementing | 任务统计 + 任务详情 `workflow`（卡在哪个子阶段） |
| accepting | `task_to_tests` + `coverage.testing` |

## 5. 压缩模式：循环检查别把整套映射塞进上下文

首次注入用**完整模式**（含映射全量），循环检查用**压缩模式**（只留统计与缺口），
约 500 tokens → 50 tokens：

```jsonc
// 完整模式（首次注入，~500 tokens）
{
  "stage": "implementing",
  "status": { "tasks_total": 5, "tasks_done": 2, "tasks_in_progress": 2, "tasks_todo": 1 },
  "task_details": [ { "id": "t-354ea0", "status": "in_progress",
                      "workflow": [ { "phase": "implement", "status": "in_progress" } ] } ]
}

// 压缩模式（循环检查，~50 tokens）——从上面同一份 RTM 折算
{
  "stage": "implementing",
  "progress": "2/5 done, 2 in_progress",
  "current_tasks": ["t-354ea0@implement", "t-abc123@implement"],
  "next_action": "继续执行 t-354ea0 的 implement 阶段"
}
```

**压缩规则**：状态统计折成一句话；任务详情只留 in_progress 任务的 id 与当前子阶段；
追溯映射只留 `uncovered`；覆盖度只留 `rate` 与缺口。

## 6. 失败与降级（FR-9）

| 情况 | 行为 |
|------|------|
| RTM 文件缺失 | 读取返回 `null`；`assembleStageOverviewRTM({ regenerator })` 会用生成器实时重建后再读 |
| YAML 格式错误 | 宽读返回 `null` 并记 `lastReadError(path)`；严格读抛 `RTMError('RTM_FILE_PARSE_ERROR')`——不静默 |
| 写入失败 | 抛 `RTMError('RTM_FILE_WRITE_ERROR')`；接线层吞掉并记 warning，**不打断需求创建/提交/确认** |
| 与台账不一致 | 以台账为准：生成器每次都从台账快照读任务状态 |
| 并发更新 | 原子写入（临时文件 + rename）；implementing 拆文件降低冲突面 |

## 7. 自检命令

```bash
# 生成引擎单测 + 端到端（7 个触发点 / 追溯链 / 性能）
cd agent-dh && npx vitest run packages/tools/reqboard/tests

# 包级类型检查
cd agent-dh/packages/tools/reqboard && pnpm build
```

## 相关页面

- [RTM 使用指南（台账内的覆盖度/验收追踪）](rtm-user-guide.md)
- [需求看板实操（从立项到归档）](reqboard-workflow.md)
- [需求节点详情系统](../architecture/reqboard-stage-detail.md)
- [Dive 模式使用](../guides/dive-mode-usage.md)
- [项目看板代码流程与实施流程](../architecture/pmboard-code-flow.md)
