---
req_id: REQ-4842fe
doc: verification
status: submitted
submitted: 2026-09-21
---
# REQ-4842fe 验收材料：长任务拆短、子任务由 workflow 串链驱动

## 1. 交付结论（一句话）

任务卡之下多了「子任务层」：父卡**开工时**自动按卡类型落子卡链（feature = 研发→联调→复核→测试），
每张子卡 = 一次独立 workflow run，链跑完父卡自动收尾、需求自动进验收；**批准计划是全链唯一的人工动作**；
失败即暂停并用**会话内弹框**请人三选一处置（不发飞书）。看板上能直接看见自动链状态与父子卡进度。

## 2. 可复核证据（2026-09-21）

| # | 验收项 | 命令 / 证据 | 结果 |
|---|---|---|---|
| 1 | 既有用例不退化 | `cd packages/pages/dsh-pmboard && npx vitest run` | **126 文件 / 1512 例全绿** |
| 2 | 真实台账副本读取 + 渲染无异常 | `npx tsx /tmp/render-check.mts`（脚本见 §3；只读副本，不碰真台账） | revision **2185** / 51 需求 / 234 任务 / 泳道 51,024 B / 列表 19,230 B，**零异常** |
| 3 | 层边界门禁 | `tests/layer-boundary.test.ts`（含在 #1）＋ `grep -rn 'ctx.workflowEngine' src` | domain 无 `node:` / `@deepseek-ai/` 运行时 import；`ctx.workflowEngine` 实现只在 `src/adapters/WorkflowEngineRunner.ts`（其余为注释） |
| 4 | 插件 schema 冒烟（宿主启动不崩） | `tests/plugin-schema.smoke.test.ts`（含在 #1） | **20/20**；本需求把 `dsh-pmboard` 补进 PLUGINS（此前不在名单 = 新工具 schema 无人编译的"假绿"） |
| 5 | 主链零点击 | `tests/auto-chain-approval.test.ts` | 批准计划后不调用任何人工工具，一路自动推进到 accepting |
| 6 | 失败暂停与弹框 | `tests/failure-handling.test.ts` | 子卡退回 + attempt+1 + 失败评论；autoRun=false；告警端口收到**弹框指令壳**；后续卡不执行 |
| 7 | 并发上限与冲突两级防线 | `tests/concurrency-limits.test.ts` / `tests/advance-chain.test.ts` | 同需求 ≤3 父卡；改动面重叠拒绝；mtime 跨卡覆盖兜底 |
| 8 | 看板父子卡与控制面 | `tests/client-subtask-view.test.ts`（11 例） | 四态徽标（运行中/已暂停/熔断/手动）、子卡链、进度口径、暂停/继续/终止 |
| 9 | 消息与尺寸门禁 | `tests/message-hygiene.test.ts` / `tests/size-budget.test.ts` | 全绿；src 单文件 ≤400 行（index.ts 恰好 400） |

## 3. 复现命令（真实台账副本渲染）

```ts
// /tmp/render-check.mts —— 只读副本，绝不写真台账
import { copyFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository } from '<pkg>/src/adapters/JsonLedgerRepository.js'
import { buildBoard, buildListView } from '<pkg>/src/client/views/board.ts'

const dir = mkdtempSync(join(tmpdir(), 'ledger-copy-'))
copyFileSync('<agent-dh>/.dsh-data/dsh-reqboard.json', join(dir, 'dsh-reqboard.json'))
const store = new JsonLedgerRepository({ file: join(dir, 'dsh-reqboard.json') })
await store.load()
const s = store.snapshot()
const state = { revision: s.revision, requirements: [...s.requirements], tasks: [...s.tasks], ready: {} }
console.log(buildBoard(state).length, buildListView(state).length)   // 渲染不抛 = 通过
```

## 4. 已知缺口（2026-09-21 用户裁定：记账不修）

- **条款映射缺失**：拆分落库时未把计划里的 FR 映射写入任务记录（`TaskRecord` 无 `requirementRefs` 字段），
  故 requirement §8 后「条款接收状态」表 16 条全红。**台账口径缺口，不影响功能与本次验收**；修法 = 按批准计划补写各任务 refs。

## 5. 过程留痕与并发说明（如实记录）

- 实施期间有**第二个窗口并发改同一个包**（`src/adapters/FailureAlert.ts`，2026-09-21 03:03 加入"弹框指令壳"
  `popupInstructionFor`）。它的 6 行拼接式文案一度让消息卫生门禁红（adapters 5→9，全量 125/1）；
  对方收手后由本窗口改为「逐行数组 + join + fmt」（**行为完全不变**）收绿至 126/0。
  该段代码非本窗口原创，本窗口只做了门禁兼容改写并如实登记在此。
- 需求文档在确认后改写过 3 处（§6.6 ×2 + §8 新增决议 #17「只有弹框」），已按用户 2026-09-21 裁定执行并留痕。

## 6. 复核补记（2026-09-21 04:05，w-d41c9696）

- **验收经过**：本文（§1~§5）由 t-fd25e0 撰写，但**从未经 `reqboard_submit(kind=verification)` 登记**，故系统里**没有验收单**。
  2026-09-21 03:50:02（CST）用户从看板以**覆盖方式**验收通过，台账原文：「人工验收通过（带覆盖：看板覆盖通过：尚无验收材料（无验收证据））」，
  需求随之自动进 `archived`。即：**本次验收是无材料、无验收单的人工覆盖通过**，逐项裁决未发生。
- **测试读数复核（2026-09-21 03:47~03:59 实跑，`packages/pages/dsh-pmboard`）**：本文 §2 第 1 行的「126 文件 / 1512 例全绿」**已不可复现**。
  同期另一窗口（w-2105d331）正在改同一工作区的「拆分计划归 decomposing」阶段门（`SubmitArtifact.ts`，未提交），
  全量读数在约 4 分钟内由 **14 文件红/61 例失败** 降至 **10 文件红/17 例失败**（移动靶，非本需求回归）。
  本需求**自有 14 个证据测试文件**复跑：**13 绿 / 1 红**（`tests/auto-chain-approval.test.ts` 4 例中 1 例红）。
  余 1 例（`decomposition 产物由批准门自动落章（门合并留痕）`）根因同在对方新契约：计划产物 kind 由 `plan` 改为 `decomposition`（`SubmitArtifact.ts:274`），
  本用例直接种 `req.plan` 而未登记该产物 → 批准门无可落章产物。
- **本窗口订正（1 行，断言未改）**：`packages/pages/dsh-pmboard/tests/auto-chain-approval.test.ts` 布景 `status: 'design'` → `'decomposing'`，随上述阶段门裁定。
- **合并去向**：`docs/architecture/reqboard-stage-detail.md` §6「子任务层与自动链控制面（REQ-4842fe，2026-09-21）」已真实写入。
