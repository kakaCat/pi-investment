# REQ-640a55 验收（verification）

> 自动生成于 reqboard_verify_submit

## 验收结论
三处「承诺了却没生效」的门禁全部落地：①三要素门禁接上执行链（task_card_incomplete 首次有真实产出路径：拆分出口 + 单卡结单）②拆分骨架与兜底骨架头直出业务三要素节 ③编号跳号 / 编号重复两处结构性死门禁修复。全量 100 文件 / 1282 条全绿，三处反向验证全部按预期变红，存量零误伤实测被拦 0 张。

## 证据清单
- 全量回归：cd packages/pages/dsh-pmboard && npx vitest run → 100 文件 / 1282 条全绿（落地前基线：97 文件 / 1250 条）
- 类型门禁：cd packages/pages/dsh-pmboard && npx tsc --noEmit → 零错误（由 packages/pages/dsh-pmboard/tests/typecheck.test.ts 覆盖）
- FR-1 工具层：npx vitest run packages/pages/dsh-pmboard/tests/triad-gate.test.ts → 13 passed（接线函数 8 + 工具层端到端 5：出口拦/出口放行/卡不存在放行/结单拦/结单放行）
- FR-1+FR-2 全链路：npx vitest run packages/pages/dsh-pmboard/tests/e2e-triad-gate.test.ts → 2 passed（需求文档→计划批准→拆分→确认产物→推进 implementing；骨架产出的卡直接过门禁；改坏一节被拦 task_card_incomplete）
- FR-2 骨架：npx vitest run packages/pages/dsh-pmboard/tests/handoff.test.ts → 9 passed（含新增断言「三要素节都在且正文非空」）
- FR-3+FR-4 编号：npx vitest run packages/pages/dsh-pmboard/tests/clause-numbering.test.ts → 15 passed（跳号/重复/多前缀/不可解析 id/标题式与加粗式定义位）
- FR-5 改卡通道：npx vitest run packages/pages/dsh-pmboard/tests/amend-acceptance.test.ts → 9 passed（旧卡 ## 验收标准 与新卡 ## 得到什么结果 各一例整段替换；无该段不硬造）
- 反向验证①：骨架节名改回 ## 目标 → packages/pages/dsh-pmboard/tests/handoff.test.ts 3 条 + 全链路 1 条变红（共 4 红），还原后全绿
- 反向验证②：判重改喂去重后的清单 → packages/pages/dsh-pmboard/tests/clause-numbering.test.ts 1 条变红（证明判据真依赖未去重来源）
- 反向验证③：跳号正则改回 (d+) → packages/pages/dsh-pmboard/tests/clause-numbering.test.ts 3 条变红（证明修的是真判据，不是测试自嗨）
- 存量零误伤实测（时点 2026-09-19T11:32Z，源 .dsh-data/dsh-reqboard.json + docs/requirements/REQ-640a55/tasks/*.md，工作区=运行实例）：非终态需求 11 条、在途卡 2 张、被结单门禁拦下 0 张、卡文件缺失 0；处于 decomposing 的需求仅 REQ-6cbbf7 且其在途卡为 0（按设计跳过）
- 需求产物：docs/requirements/REQ-640a55/requirement.md（5 条功能点）+ docs/requirements/REQ-640a55/design/architecture.md、data-model.md、interfaces.md、test-cases.md + docs/requirements/REQ-640a55/plan.md + docs/requirements/REQ-640a55/decomposition.md
- 任务卡：docs/requirements/REQ-640a55/tasks/t-92e0b3.md、t-c8fb87.md、t-fb5e66.md、t-11e56a.md、t-ad7826.md（5 张均已补业务三要素节）
- 代码改动文件：packages/pages/dsh-pmboard/src/application/internal/content-gate-triad.ts（新增 86 行）、content-gates.ts、content-gate-wiring.ts、src/application/use-cases/Decompose.ts、ReportTask.ts、AmendTaskAcceptance.ts、src/tools/MoveTool/MoveTool.ts、src/tools/TaskMoveTool/TaskMoveTool.ts
- 代码提交（分支 feat/pmboard-triad，worktree .claude/worktrees/pmboard-triad）：2cf2b57e、4792fccd、6e4a2224、4f4af257、f7c8696d、d5195b70（相对快照 18 文件 / +653-34）
- 运行实例已生效：同一份改动已落盘到 agent-dh 工作区，并在 packages/pages/dsh-pmboard 执行 pnpm build:client → 输出 [verify-client] OK bundle=229219 bytes（关键符号齐全）
- ⚠️ 基线说明（验收需知）：分支架在快照提交 14bc211a 之上——它封存了主工作区 1146 个未提交改动（非本需求产出，含已归档需求 REQ-81aabd 的 planning→design 改名代码）。真身提交后执行 git rebase --onto <真身> 14bc211a feat/pmboard-triad 即可丢掉快照层
- ⚠️ 两条已知工具限制（已留痕 memory_write，均不在本需求范围内）：① worktree 改动对 done 凭证门不可见（按运行实例工作区 stat），故需把修复同步落盘实例工作区再结单；② 改卡通道在终态任务上会「先改台账、后以 invalid_transition 失败」，且卡文档同步失败被 catch 静默吞掉——已手工对齐并记为后续需求候选

## 边界与遗留

**本轮不做**：不回溯改写已归档/已验收的存量卡；不改 `support.ts` 的同步结单证据校验（只走工具壳异步预检）；
不新增门禁类型、不改提示词片段（本次只让实现追上提示词已有承诺）；不做卡的文风评判（标题像工程名词堆叠只警告不阻断）。

**遗留（另立需求）**：
1. 改卡通道对**终态任务**没有独立入口——借道 `task_move` 会在转移校验前先改台账，出现「被拒绝的调用留下副作用」；
2. 卡文档同步失败被 `catch {}` 静默吞掉 → 台账与人读的唯一事实源会漂移且无人报错（本次手工对齐）；
3. 跨工作区（worktree）开发时，`done` 凭证门按运行实例工作区 stat 文件，需额外落盘步骤。
