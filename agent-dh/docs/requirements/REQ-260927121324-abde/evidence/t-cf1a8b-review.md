# t-cf1a8b 复核记录（REQ-260927121324-abde · 父卡 t-a6293c「读路径把快照缺失与不可得同等计入 degraded」· 阶段 review）

> 验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据。
> 总判定：**设计 4 个判定点全部落位，源码层无偏离**；另发现 **1 条交付面阻断项 D-1（dist 陈旧，线上 FR-7 未生效）** + 3 条观察项（均不影响源码判定）。

## 0. 复核对象与设计基线（R-013 标注来源）

**设计基线**（均为 REQ-260927121324-abde）：
- requirement.md L222-227（FR-7 快照缺失如实降级）；
- design/data-model.md L82-109（`hasSnapshotGap` 判定式 + 三点纪律）；
- design/backend.md L70-75（读路径降级实现，明确「不改 byStage/executions/totals」）；
- design/architecture.md L76-77（根因 R3）、L169-170（FR-7 实现要点）；
- 任务卡 tasks/t-a6293c.md L16-19（得到什么结果 / 实施方案）。

**实现**（工作区根 = /Users/yunpeng/pi-investment/agent-dh）：
- packages/web/dsh-pmboard/src/application/query/QueryRequirementToken.ts（本卡唯一变更文件，git diff 仅 2 处 hunk）；
- 契约面 packages/web/dsh-pmboard/src/shared/protocol.ts:1763（`degraded: boolean`，未改）、消费面 src/client/token-info.ts:63（未改）。

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | `hasUnavailableSnapshot` 替换为 `hasSnapshotGap`（backend L72；任务卡 L19） | `:39` 函数定义改名；全仓 grep `hasUnavailableSnapshot` 在 src 命中 0（旧函数体已删，非并存） | **无偏离** |
| R2 | ①需求侧：任何一条状态事件缺 `tokenSnapshot` 或 source 非 projection → gap（data-model L87-90；requirement L224） | `:40-42` `for (const e of req.statusHistory ?? []) { if (e.tokenSnapshot === undefined \|\| e.tokenSnapshot.source !== 'projection') return true }` 与设计逐字一致；`source` 类型为 `'projection' \| 'unavailable'`（protocol.ts:1685），故 `!== 'projection'` 覆盖「不可得」与「写了其它值」两形态 | **无偏离** |
| R3 | ②任务侧：运行中（endedAt 缺省）要求 start 可得；已闭合要求 start/end 均 projection，否则 gap（data-model L91-98） | `:44-49` `const startOk = e.tokenUsage?.start?.source === 'projection'` / `endOk = ...end...` / `if (e.endedAt === undefined ? !startOk : !(startOk && endOk)) return true`，与设计逐字一致；旧实现 `u === undefined → continue`（整条执行记录无快照时漏报）正是本次要消除的漏报分支，已改为 gap | **无偏离** |
| R4 | `degraded = req.tokenUsage 为 undefined \|\| hasSnapshotGap(req, ledger)`（data-model L102；任务卡 L19） | `:106` `degraded: usage === undefined \|\| hasSnapshotGap(req, ledger)`；`usage = req.tokenUsage`（`:88`），两处取值之间无副作用，语义等价 | **无偏离**（字面差异见 O-3） |
| R5 | 不改 byStage/executions/totals 装配逻辑与对外形状，degraded 仍是 boolean（backend L74-75；data-model L107-109） | `git diff` 仅两处：`:33-52` 函数本体（含补注释）+ `:106` 一行；`executionRows`/totals 兜底/byStage 装配零改动；protocol.ts `RequirementTokenView.degraded: boolean` 未改；无新增/改名/删除字段 | **无偏离** |

**结论：源码层无偏离。** 依据：上表 5 条逐条与 data-model L82-109 判定式逐字比对一致；`git diff` 只触及设计指定的两点（函数体与 degraded 表达式），未越出任务卡 L19「不改装配逻辑与对外形状」的边界。

---

## 2. 交付面发现 D-1（阻断父卡「线上 degraded 由 false 变 true」这一验收项）

- **现象**：`curl -s http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-260927100007-b8ba/token` → `degraded:false`（实测 2026-09-27 14:5x，本次复核）。
- **台账事实**（读 `.dsh-data/dsh-reqboard.json`）：该需求 7 条状态事件中 `implementing` 一条 **缺 tokenSnapshot**；16 条已闭合执行记录的 `start`/`end` **全为 MISSING** → 按新判定式应返回 `degraded:true`（FR-7 验收要求的正是这条曲线由 false→true）。
- **根因**：运行实例按 `package.json main = ./dist/index.mjs` 加载编译产物；`dist/index.mjs`（mtime 2026-09-27 14:07）内 `hasSnapshotGap` 命中 **0** 次、`hasUnavailableSnapshot` 命中 **2** 次；而源文件 mtime **14:52**（晚于 dist）——即「源码已改、产物未重建」，运行实例仍是旧语义。
- **判定**：这不是设计与源码实现的偏离（源码与设计一致），而是**发布落点未闭环**（对齐工程教训「改 dist 包源码必须 pnpm build 才生效；源码级测试不能证明线上行为」）。`tests/token-degraded-integration.test.ts` 经 vitest 直载 src 全绿，不能替代线上证据。
- **建议处置**（本卡不越界执行——重启 :13080 会中断当前会话）：`cd packages/web/dsh-pmboard && pnpm build` → 重启实例 → 复验同一 curl `degraded:true`；由测试卡 t-073d46 / 父卡收口阶段执行，或回派研发卡补构建。**在该复验通过前，父卡「得到什么结果」的 curl 验收项视为未达成。**

---

## 3. 观察项（不阻断、不影响本卡源码契约）

- **O-1 单测落点**：FR-7 要求的「事件缺 tokenSnapshot → true」「执行缺 start/end → true」当前由联调 HTTP 用例 `tests/token-degraded-integration.test.ts`（9 例，覆盖缺事件快照 / unavailable / 运行中缺 start / 已闭合缺 end）与既有 `tests/token-endpoint.test.ts`（全投影→false、无 tokenUsage→true）承载；专门单测卡 **t-073d46 仍为 todo**，尚未落盘。不影响本卡结论，测试卡落地后覆盖更直接。
- **O-2 边界矩阵缺一例**：联调覆盖「运行中缺 start」「已闭合缺 end」，未单列「已闭合但缺 start（end 有）」；表达式 `!(startOk && endOk)` 对该形态对称覆盖，「无偏离」判定不变，可在测试卡补一例。
- **O-3 字面差异**：design L102 写 `req.tokenUsage === undefined`，实现经局部变量 `usage` 判断；取值点之间无写操作，语义等价，**非偏离**。

---

## 4. 复跑证据（本次复核实测，2026-09-27）

    $ cd packages/web/dsh-pmboard
    $ npx vitest run tests/token-endpoint.test.ts tests/token-fallback.test.ts tests/token-degraded-integration.test.ts
     ✓ tests/token-endpoint.test.ts (6 tests) / ✓ tests/token-fallback.test.ts (3 tests)
     ✓ tests/token-degraded-integration.test.ts (9 tests)
     Test Files 3 passed (3) / Tests 18 passed (18)

    $ cd /Users/yunpeng/pi-investment && git diff -- agent-dh/packages/web/dsh-pmboard/src/application/query/QueryRequirementToken.ts
     仅 2 hunk：:33-52 hasUnavailableSnapshot → hasSnapshotGap（含注释）· :106 degraded 表达式；装配逻辑未动

    $ grep -c hasSnapshotGap dist/index.mjs        → 0
    $ grep -c hasUnavailableSnapshot dist/index.mjs → 2
    $ stat -f '%Sm %N' src/application/query/QueryRequirementToken.ts dist/index.mjs
     src 14:52:15 > dist 14:07  → 产物陈旧（D-1 依据）

    $ curl -s -m 8 http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-260927100007-b8ba/token
     data.degraded=false（与旧 dist 一致；台账实存 1 缺事件快照 + 16 缺 start/end）

---

## 5. 结论

- **设计 → 实现 5 条落点（R1–R5）全部到位，无偏离**：改名并删旧函数、需求侧「缺失或非 projection 即 gap」、任务侧「运行中要求 start / 已闭合要求 start+end」、degraded 表达式、以及「装配逻辑与对外形状不变」，逐条与 data-model L82-109 + backend L70-75 + 任务卡 L19 一致。
- **D-1 阻断父卡线上验收项**：dist 产物陈旧导致运行实例仍执行旧语义（curl degraded=false），需 `pnpm build` + 重启后复验 true；源码无需返工。
- 3 条观察项均不改变契约（O-1 专门单测待 t-073d46、O-2 补一例对称边界、O-3 字面等价）。

复核人：实施子代理（t-cf1a8b·复核）；时间：2026-09-27 15:0x (+08:00)
