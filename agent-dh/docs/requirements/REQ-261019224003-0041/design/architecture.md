# 架构设计 · REQ-261019224003-0041

> serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-8
> 事实与锚点全部来自 dsh-pmboard 仓 `docs/strategy-research/workprocess-integration/`（下称 01/02/03），本文不重复抄事实，只定形态。

## 1. 总体形态（serves: FR-1, FR-2）

- WP 仓（`/Users/mac/Documents/ai/dsh/dsh-workprocess`）四包整体搬入 dsh-pmboard 仓 `workprocess/`，目录名与层级照抄：
  `workprocess/workprocess/`（内核+客户端半）、`workprocess/workprocess-round-driver/`、`workprocess/tool-workprocess/`、`workprocess/command-workprocess/`（包名 `dsh-command-workprocess` ≠ 目录名）。
- 装载形态：profile 只列 `dsh-pmboard` 一个 bundle；`pm/cordis.patch.yml` 从 1 行变 5 行（insert：`pmboard` + 四包），pm 的 patch 身份变为"pm 全家桶装载清单"（02-options §A1）。
- 四包间 `workspace:*` 依赖图原样成立（同一 workspace 根硬约束自然满足，01-facts §1.4）。

## 2. 运行时结构（serves: FR-5, FR-6）

```
pm 台账（需求/子卡/运行态，唯一真源）
   │  每拍重建（纯函数，零 I/O）
   ▼
projectWorkProcess() 投影器 ──▶ WorkProcess 快照（facts）
                                   │  decide.ts 纯函数决策
                                   ▼
                        workprocess-round-driver（驱动器）
                                   │  决策=写动词/投递文案
                                   ▼
              写回只经 pm 用例（AdvanceChain/ExecuteTask/…） ＋ 投递走 pm 现有投递器
                                   │
              回合账/asked 记号/closedAt ──▶ workprocess 存储域（scope=需求 id）
```

- 进程内只有一份 workprocess 内核（由装载器装载）；pm 侧**不内联内核实现**进 dist 当第二份（B2 形态已否，01/02 有证）——`pm/tsdown` 的内联是为"包在产物里可解析"，领域状态仍只经 `ctx.workprocess` 服务面。
- Dive 许可语义与 workprocess `activation` 合并成一套；pm 侧失败退避/闭锁若要留，作为"投递健康闸"并入 GateFacts（03 §四）。

## 3. 分层与边界（serves: FR-4）

- L1：`workprocess`（零依赖内核，`pm-core` allow 放行——"内核当库"是既定意图，01-facts §2.2 缺口 2）；`pm-core` 可直接 import 内核纯函数/类型。
- L2：`workprocess-round-driver` / `tool-workprocess`（allow `workprocess`）；命令包补入 L2。
- `pm-core/src/application/dive-core/round-state.ts` 的回合契约归属从 goal 改指 workprocess 定义处（03 §五）。
- `pm/src/adapters/goal-round-lifecycle.ts` / `goal-round-ports.ts` 整体换成 workprocess 驱动器 + 投影/写回适配（03 §五）。

## 4. 与 pm 固定阶段的关系（serves: FR-6）

- 需求级状态机与人工门**不动**（`move`/`ask_confirm`/验收单/归档）；workprocess 只管 implementing 期"卡执行"的回合推进（裁定 #5）。
- `reqboard_task_run` 保留为起链入口（人或 agent 触发一次）；"谁决定下一拍"移交驱动器。
- 子卡 DAG 不映射进 workprocess：一子卡 = 一 workTask，执行顺序由 pm 的 ready 集合定，投影器把 `nextReady` 折进阶段事实（裁定 #2）。

## 5. 废弃清单（serves: FR-8）

- `goal/*`（51 文件）、`pm-workflow/`（9 文件）保持删除不复活。
- 17 个 `import pm-goal*` 活文件改接 `ctx.workprocess` 服务面或摘除（清单见 01-facts §3.2）。
- 配置面旧名三组映射（tsconfig/vitest 两处）与 boundary 的 `pm-goal` 行一并摘除。
