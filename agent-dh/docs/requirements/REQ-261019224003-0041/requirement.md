# REQ-261019224003-0041 改用 dsh-workprocess 的内容（收编四包 + 投影接缝驱动 pm 子卡执行）

> **实施仓库**：`dsh-pmboard` 仓（`/Volumes/ORICO/doc/github/dsh/dsh-pmboard`）；本台账在 agent-dh。
> 调研三件套已齐备并获人裁定（2026-10-19，本窗口对话裁定，见下"裁定记录"）：
> 事实账、候选路径、接缝设计均在 dsh-pmboard 仓 `docs/strategy-research/workprocess-integration/`
> （`01-facts.md` / `02-options.md` / `03-seam-design.md`，下文简称 01/02/03）。
> 本文只写需求面（边界/定义/角色/功能点/验收），实现细节在 design 阶段展开。

## 裁定记录（brainstorming 阶段，对话确认）

| 裁定项 | 来源 | 裁定结果 |
|---|---|---|
| 收编路径 | 02-options §六 #1 | **A1**：四包原样收进 dsh-pmboard 仓 `workprocess/*`，profile 只装一个 `dsh-pmboard` |
| 真源与接法 | 03-seam-design §六 #1 | **i 投影**（pm 台账为真源，workprocess 只持回合运行态） |
| 子卡 DAG ↔ 阶段串行 | 03 §六 #2 | **一子卡 = 一 workTask**，执行顺序由 pm 的 ready 集合定 |
| blocked/paused 与 closePolicy 落点 | 03 §六 #3 | **pm 卡面加字段**（`blockedReason`、`closePolicy`） |
| 投递与许可归谁 | 03 §六 #4 | **投递用 pm 现有投递器，许可与 Dive 合并** |
| 需求级固定阶段 | 03 §六 #5 | **保持**（workprocess 只管 implementing 期卡执行；归档仍走 pm 人工门） |
| 范围 | 02 P1–P7 | **P1–P6**，P7（客户端半并入）另开需求 |

## 一句话目标（L1）

把 `dsh-workprocess`（WP 仓 = `/Users/mac/Documents/ai/dsh/dsh-workprocess`）的四个包整体收进 dsh-pmboard 仓 `workprocess/*`，装载形态改为 profile 只装一个 `dsh-pmboard`，pm 以**投影接缝**用 workprocess 回合驱动器接管 implementing 期子卡执行的"谁决定下一拍"，同时完成 `goal/*` 与 `pm-workflow` 退役收尾。

**可证伪判定标准**（全部可跑，在 dsh-pmboard 仓根执行）：
1. `pnpm install && pnpm boundary:check` 退出码 0（"清单声明了却找不到包目录"的 6 条红消失，对照 01-facts §二）；
2. `pnpm typecheck` 中 workprocess 相关 error = 0，且 goal 家族旧名红清零（`grep -rlE "from '(pm-goal|tool-pm-goal)" --include='*.ts' . | grep -v node_modules | wc -l` = 0）；
3. `pnpm --filter dsh-pmboard build` 后 `grep -c "workprocess" pm/dist/index.mjs` > 0 且 `grep -c 'from "workprocess' pm/dist/index.mjs` = 0（内联、无裸说明符）；
4. 装载组合复现：`composeEntries` 结果出现 5 条 entry（pmboard + 四包）、`skippedBundles` 为空；重启宿主后六个 `*_workstage` / `*_worktask` 工具在；
5. 真机跑一条全 auto 流程：阶段自动开工/收口，`~/.dsh/storages/workprocess.json` 里 `closedAt` 落下（流程收口）。

## 边界（L2）

**做**（对应 02-options 的 P1–P6）：
- 四包（`workprocess` / `workprocess-round-driver` / `tool-workprocess` / `command-workprocess`）源码从 WP 仓整体搬入 dsh-pmboard 仓 `workprocess/`（目录名与层级照抄，含 tests/client/tsconfig/tsdown/cordis.patch.yml）；
- `pm/cordis.patch.yml` 给 5 条 insert 装载行；`pm/package.json` 增四包 `workspace:*` 依赖；`pm/tsdown.config.mjs` 内联正则增四条；`tsconfig.json` / `vitest.base.mts` / `vitest.config.ts` 补齐命令包映射；boundary 清单 `pm-core` allow 放行 `workprocess`；
- 投影接缝落地：pm 台账为真源，新增纯函数投影器（pm → workprocess 事实），写回只经 pm 用例；回合账落 workprocess 存储域（scope = 需求 id）；`reqboard_task_run` 保留为起链入口，"下一拍"推进职责交 workprocess 驱动器；Dive 许可语义与 workprocess `activation` 合并；pm 卡面新增 `blockedReason` / `closePolicy` 字段；
- `goal/*` 与 `pm-workflow` 收尾：17 个仍 `import pm-goal*` 的文件改接 workprocess 服务面或摘除；配置面旧名三组映射与 boundary 的 `pm-goal` 行摘除；两个包保持删除不复活。

**不做**（明确排除）：
- P7 可选收敛步（把 workprocess 客户端半并入 `dsh-pmboard` 的 client bundle、装载行收到 1 行）——另开需求；
- 不改 pm 需求级固定阶段状态机与人工门（`move` / `ask_confirm` / 验收单 / 归档不动，裁定 #5）；需求级不交给 workprocess 拆；
- 不改 workprocess 驱动器内核决策树（裁定 #1 选投影而非参数化，`TickDeps.domain` 不动）。

**轻档 → 重档升级说明（L3）**：本需求触发升级信号——要动架构（四包跨仓搬迁、装载形态从"四包独立装载"改写为"单包 5 行"）、要改数据模型（pm 卡面加字段）；裁定项虽已在对话中裁定完毕，改动面仍是重档量级。按 L3 单向升级规则按重档推进，不反向降级。

## 产品定义

dsh-pmboard 从"自带 goal 回合机械 + pm-workflow"切换为"workprocess 回合驱动器驱动"：需求级仍是 pm 的固定阶段流水线（draft→…→archived，人工门不动），**implementing 期的子卡执行回合由 workprocess 驱动器接管**——pm 台账（需求/子卡/运行态）是唯一真源，workprocess 侧只持回合运行态（逐任务回合账、许可、去重记号、closedAt），每拍由纯函数投影器把 pm 台账投影成 workprocess 事实，驱动器决策后写回只经 pm 用例。

## 用户与角色

- **dsh-pmboard 仓维护者**：执行搬迁与接缝落地，靠 P1–P6 的可跑判据验收每一步；
- **宿主（desktop/web/agent-dh profile）**：装载面从"`dsh-pmboard` + 四条独立 bundle"收敛为"只列 `dsh-pmboard`"，装载清单由 `pm/cordis.patch.yml` 的 5 条 insert 行提供；
- **agent（pm 流程执行者）**：`reqboard_task_run` 仍是起链入口；起链后"下一拍"由 workprocess 驱动器决定，投递走 pm 现有投递器；
- **人（批准者）**：需求级人工门不变；blocked 任务的预算追加经 workprocess `resume` 语义（+1 份回合预算）。

## 功能点

- **FR-1: 四包源码收编**——WP 仓四个包整体搬入 dsh-pmboard 仓 `workprocess/`（目录名与层级照抄）；`pnpm-workspace.yaml` 的 `workprocess/*` glob 真实匹配到四个目录。
- **FR-2: 装载形态收敛**——`pm/cordis.patch.yml` 提供 5 条 insert 行（`pmboard` + `workprocess` / `workprocess-round-driver` / `tool-workprocess` / `dsh-command-workprocess`，id/name/config 照抄各包现有 patch，工具面与驱动器的 `blockedAfterRounds` 同值）；profile 只列 `dsh-pmboard` 一个 bundle；客户端半随 `workprocess` 那条 entry 进浏览器。
- **FR-3: 依赖与内联构建**——`pm/package.json` 增四包 `workspace:*`；`pm/tsdown.config.mjs` 的 `WORKSPACE_PACKAGES` 增 `/^workprocess/`、`/^workprocess-round-driver/`、`/^tool-workprocess/`、`/^dsh-command-workprocess/`；产物内联且无裸说明符残留。
- **FR-4: 配置面与分层清单对齐**——`tsconfig.json` / `vitest.base.mts` / `vitest.config.ts` 补齐四包（含命令包）映射与 include；`scripts/package-boundary-check.mts` 的 `pm-core` L1 allow 增 `workprocess`，L2 放行其余三包；`boundary:check` 转绿。
- **FR-5: 投影接缝（pm 台账 → workprocess 事实）**——pm-core 新增零 I/O 纯函数投影器（输入需求 id/任务/运行记录，输出 `WorkProcess` 快照）；写动词逐一对表到 pm 用例（写回只经用例，不直写 pm 存储）；回合账 / `asked` 耐久记号 / `closedAt` 落 workprocess 存储域，scope = 需求 id；不一致即对账告警，绝不静默。
- **FR-6: 驱动接管与许可合并**——`reqboard_task_run` 保留为起链入口（人或 agent 触发一次）；"谁决定下一拍"由 workprocess 驱动器接管；Dive 的许可语义与 workprocess `activation` 合并成一套；投递复用 pm 现有投递器（适配层只取文案与决策）。
- **FR-7: pm 卡面字段扩展**——任务卡新增 `blockedReason`、`closePolicy` 字段（含显示面），承载 workprocess 的 blocked/paused 与 closePolicy 语义。
- **FR-8: goal/pm-workflow 退役收尾**——17 个 `import pm-goal*` 文件改接 `ctx.workprocess` 服务面或摘除；`pm/src/adapters/goal-round-lifecycle.ts` / `goal-round-ports.ts` 整体换成 workprocess 驱动器 + 投影/写回适配；`pm-core/src/application/dive-core/round-state.ts` 的回合契约归属从 goal 改指 workprocess；配置面旧名三组映射与 boundary `pm-goal` 行摘除；`goal/*`、`pm-workflow/` 保持删除不复活。
- **FR-9: 可跑验收面**——每条 FR 有对应判定命令（见"验收"节）；验收以命令读数为准，不以"应该没问题"收尾。

## 接口（对外入口，设计阶段细化）

- **服务面**：`ctx.workprocess`（17 个写动词逐一对表 pm 用例）+ `work/changed` 事件；错误语义沿用 workprocess 服务现有约定（设计阶段逐动词列表）。
- **投影器**：纯函数 `projectWorkProcess(requirementId, tasks, runs) → WorkProcess`，零 I/O，落 pm-core domain/application 层。
- **工具面**：六个 `*_workstage` / `*_worktask` 工具与 `reqboard_task_run` 并存；后者语义收窄为"起链入口"。
- **命令面**：`/work`（`dsh-command-workprocess`）随装载清单一并进来。

## 数据契约与迁移兼容

- workprocess 存储域 `~/.dsh/storages/workprocess.json` 继续被写（同 scope 口径，已有数据不迁移）；
- pm 台账新增字段 `blockedReason` / `closePolicy`：默认空，旧数据兼容（缺失即空），回滚路径 = 字段停用 + git revert；
- profile 迁移：desktop profile 的四条 workprocess bundle 行可摘除（由 `pm/cordis.patch.yml` 提供），回滚 = 还原 profile 与 patch 文件。

## 验收（可执行判定）

逐条对应 L1 的五条判定标准（boundary / typecheck / build grep / composeEntries + 重启工具面 / 真机 auto 流程收口），另加：
- FR-5/FR-6 的接缝验收：真机跑一条两阶段全 auto 流程，阶段自动开工/收口、`closedAt` 落账；`reqboard_task_run` 手动触发一次后驱动器自走下一拍；
- FR-8 的收尾验收：`grep -rlE "from '(pm-goal|tool-pm-goal)"` = 0 且 `pnpm typecheck` 退出码 0。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1 |
| FR-2 | ✅ 已接收 | t3 |
| FR-3 | ✅ 已接收 | t2 |
| FR-4 | ✅ 已接收 | t2 |
| FR-5 | ✅ 已接收 | t5 |
| FR-6 | ✅ 已接收 | t5 |
| FR-7 | ✅ 已接收 | t4 |
| FR-8 | ✅ 已接收 | t6 |
| FR-9 | ✅ 已接收 | t7 |

> 无未接收条款（9 条全部有落点）。

<!-- reqboard:marks:end -->
