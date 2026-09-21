---
req_id: REQ-4842fe
doc: design/architecture
serves: FR-3, FR-4, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-14
status: design
---

# REQ-4842fe 设计 · 架构：子任务层与事件链自动驱动

## 1. 现状与目标结构  `serves: FR-11`

**现状（2026-09-20 实读代码事实）**：

| 环节 | 现状 | 文件 / 证据 |
|---|---|---|
| 自动执行入口 | 直连被禁用的工具 `ctx.tools.workflow` | `src/tools/TaskExecuteTool/TaskExecuteTool.ts:93`；活动配置 `tool-workflow disabled:true` |
| 生成脚本 | 用了引擎不存在的 `ctx.subagent` | `generate-workflow-script.ts:8`；引擎 `lib/worker.cjs` 只注入 agent/parallel/pipeline/phase/log |
| 状态闭环 | 执行完不动任务状态、不写凭证 | TaskExecuteTool 全程无 task_move / task_report 调用 |
| 依赖调度 | readyTasks 只供 GUI 展示，无执行器消费 | `src/shared/protocol.ts` readyTasks（注释自述"串行调度器的选择器"） |
| 运行状态机 | 需求无回退上游路径 | `RequirementStatus.ts:61` `implementing: [accepting, canceled]` |

**目标结构**：把"执行"拆成两半——**枝干（调度）留在插件宿主代码，叶子（干活）交给 DSH Workflow 引擎**。

```
  插件宿主（本仓 TS 代码，可读写台账、可调工具、可长活）
    ├─ 推进事件执行器 AdvanceExecutor  ← 枝干：状态机 + 调度 + 凭证 + rollup
    │     └─ 每张子卡一次调用 ↓
    └─ WorkflowRunner 端口 ──→ ctx.workflowEngine.start(script)  ← 叶子：子代理干活
```

**为什么枝干不能用 workflow 脚本**（结论依据）：workflow 脚本运行在 worker 线程的 vm 里，只暴露 `agent / parallel / pipeline / phase / log` 五个 hook——不能调工具、读不到台账、改不了状态；且引擎不支持嵌套 run（脚本无 `workflow()` hook）。见 `design/workflow-engine-contract.md`。

## 2. 分层与组件边界  `serves: FR-4, FR-11`

沿用本仓既有 DDD 四层（规则向内），新增三个单点：

| 层 | 新增 / 改动 | 职责（一句话） |
|---|---|---|
| domain | `domain/task/SubtaskTemplate.ts`（新）、`domain/task/TaskStatus.ts`（改：子卡转移表）、`domain/requirement/RequirementStatus.ts`（改：加一条转移）、`domain/limits.ts`（改：并发上限、熔断阈值） | 纯规则：模板映射、转移合法性、上限与阈值常量 |
| application | `application/use-cases/AdvanceChain.ts`（新）、`application/ports.ts`（改：加 WorkflowRunner 端口）、`application/use-cases/ExecuteTask.ts`（新，叶子编排） | 编排：一步推进事件的完整流程 |
| adapters | `adapters/WorkflowEngineRunner.ts`（新） | 唯一接触 `ctx.workflowEngine` 的地方 |
| tools | `tools/AdvanceTool/`（新，工具名 `reqboard_task_run`）；`TaskExecuteTool` 改为薄壳或下线 | 对外接口 |

**边界纪律**：`ctx.workflowEngine` 只允许出现在 adapter 内；domain 不得 import 任何 `@deepseek-ai/*` 运行时；工具壳不得出现状态比较（沿用既有 layer-boundary 门禁口径）。

## 3. 叶子执行：消费 workflow 引擎  `serves: FR-4, FR-6`

**调用方式（与现状的关键差异）**：

```ts
const run = ctx.workflowEngine.start({
  script,                       // 纯 JS 脚本体，只用五个 hook
  meta: { name, description, phases },
  args: { subtask },            // 纯 JSON 数据
  parent: exec.agent,           // 子代理归属调用者
  signal: exec.signal,          // 取消桥接
})
const result = await run.result   // 不 reject：stopReason 表达 error/cancelled
await run.dispose()               // 调用方负责，finally 兜底
```

**生成脚本的形状**（一张子卡 = 一次 run = 一个主执行子代理 + 可选复核子代理）：

```js
phase("执行");
log("子卡 dev 开工");
const out = await agent(`<阶段提示词：含父卡实施方案 + 本卡验收标准>`,  { schema: undefined });
return { ok: out !== null, output: out };
```

**产出提取**：run 的返回值经 realm 物化（仅接受 lossless JSON）→ 调度器据此生成子卡 report（filesChanged / 命令 / 证据摘要）→ 过子卡凭证门 → 子卡 done。

**硬约束**：脚本内不得出现 `ctx.`、`subagent`、任何工具名；由静态门禁在生成后立即校验（见 test-cases 契约用例）。

## 4. 事件链自动驱动  `serves: FR-11, FR-12`

**推进事件（Advance Event）定义**：一次事件 = 一个需求上的一小步，类型固定为：

| 事件类型 | 做什么 |
|---|---|
| OPEN_PARENT | 取 ready 父卡（todo 且依赖全 done，受上限约束）→ 自动开工 + 懒展开子卡链 |
| RUN_SUBTASK | 取该父卡链上 ready 子卡 → 一次 workflow run → 回写 + 子卡 done |
| FINALIZE_PARENT | 链全 done → 汇总 report → 父卡凭证门 → 父卡 done |
| ROLLUP | 全父卡 done → 需求自动进 accepting（停下） |
| PAUSE | 触发暂停（失败 / 熔断 / 人工关闭） |

**触发链**：批准计划（人工门）→ 落库任务表 → 触发首个事件；**每个事件结束时自动触发下一个**，直到 PAUSE 或 ROLLUP。

**载体与并发控制**：
- 执行器为插件宿主内的异步循环；**每需求单飞**（同需求同时只允许一个事件在跑，用进程内锁 + 台账 `advance.lockAt` 双保险）；
- **幂等**：事件选择的依据全部来自台账状态，重复触发只会得到"无事可做"，不会重复干活；
- **恢复扫描**：进程启动 / 面板重启后，扫描 `autoRun=true` 且未到 accepting 的需求，续跑下一个事件（崩溃不丢链）；
- **停滞熔断**：同一需求连续 N 次事件无台账状态变化 → 自动 PAUSE + 告警（防死循环烧 token）。

## 5. 失败、暂停与返工  `serves: FR-7, FR-13, FR-14`

**失败分类与判定**：

| 类型 | 判定 | 处置 |
|---|---|---|
| 子代理无产出 | `agent()` 返回 null | 子卡失败：退回 todo + attempt+1 + 失败评论 |
| run 异常/取消 | stopReason 非 completed | 同上 |
| 产出不合格 | 凭证门三项校验任一不过 | 同上 |
| 跨卡覆盖 | 文件 mtime 落在另一在跑父卡的执行窗口内 | 同上 + 冲突标记 |

**暂停语义（不自动重试）**：任一失败 → 子卡退回 + attempt+1 + 评论 → 需求 `autoRun=false` → 高优告警 + 会话内弹框处置（重跑 / 退回上游重描述 / 取消）→ **不触发下一事件**。

**返工回上游**：需求 `implementing → design`（人工门，新增）→ 重新描述需求 → 重新提交并批准计划 → **就地更新**既有父卡（不新增卡）→ 重新触发事件链。卡片修订与回滚动作逐条写入 `revisions`。

## 6. 并发与冲突  `serves: FR-9, FR-10`

- **层级**：父卡层并行（由父卡 dependsOn 决定）；子卡层串行（链内 dependsOn）；**子卡依赖不跨父卡**；
- **上限**：同需求同时 in_progress 父卡 ≤ `MAX_PARALLEL_PARENTS`（默认 3，`domain/limits.ts`）；超出的 ready 父卡排队等下一轮 OPEN_PARENT；
- **冲突防线一（拆分期，主）**：互无依赖父卡的 implementation 文件路径集合有交集 → decompose 拒绝；
- **冲突防线二（运行期，次）**：子卡 filesChanged 某文件 mtime 落在另一在跑父卡的子卡执行窗口内 → 判跨卡覆盖 → 该子卡失败；
- **诚实边界**：mtime 只证明"文件被改过"，不证明内容正确；本纪律防静默覆盖，不替代人工 review。

## 7. 风险与缓解  `serves: FR-11, FR-13`

| 风险 | 缓解 |
|---|---|
| 长链跑飞、token 燃烧 | 停滞熔断 + 每需求单飞 + autoRun 开关可随时关 |
| 事件重复触发导致重复干活 | 幂等选择（状态即事实）+ 单飞锁 |
| 进程崩溃中断链 | 台账持久化 + 启动恢复扫描续跑 |
| 子代理产出无法验证 | 子卡凭证门三项校验（report / 文件 mtime / run stopReason） |
| 自动链带病交付 | 失败即暂停、不进验收；验收仍由人工裁决 |
| 误判冲突 | 冲突仅"判失败并交人"，不自动改文件 |
| 回滚 | autoRun 置 false 即回手动模式；已落子卡仍可手动 task_move 推进 |

## 8. 与既有能力的接线点  `serves: FR-3, FR-8, FR-11`

| 既有能力 | 接线 |
|---|---|
| `reqboard_ask_confirm(target=plan)` | 批准即触发首个推进事件（并在弹框文案写明"批准后自动拆分并开跑"）；`decomposing>implementing` 由人工门改为随批准放行 |
| `reqboard_decompose` | 落库后不再请人二次确认；直接进入事件链（任务表与已批准计划 key 必须一致） |
| `applyTaskRollup`（既有） | 父卡 done 触发；语义不变，只是调用者从"窗口手动 task_move"变成"执行器 FINALIZE_PARENT" |
| `assertDoneEvidence`（既有） | 子卡用新口径（见 data-model §4）；父卡沿用汇总口径 |
| `readyTasks`（既有） | 被执行器消费，成为真正的调度选择器 |
