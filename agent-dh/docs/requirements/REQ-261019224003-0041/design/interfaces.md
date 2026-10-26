# 接口设计 · REQ-261019224003-0041

> serves: FR-2, FR-3, FR-5, FR-6, FR-7
> 锚点：03-seam-design §二（映射表）/§三（端口清单）为权威底稿，本文落定签名与错误语义。

## 1. 投影器（新增，pm-core）（serves: FR-5）

```ts
// pm-core/src/application/（零 I/O 纯函数；application 层禁 node:，IO 由调用方注入）
function projectWorkProcess(
  requirementId: string,
  tasks: readonly PmTaskCard[],      // pm 子卡（含 depends_on / max_rounds / blockedReason / closePolicy）
  runs: readonly PmRunRecord[],      // pm 运行记录（nextReady / pauseReason / lastRun）
): WorkProcess                         // workprocess 内核类型（L1 import）
```

- 入参纯数据、输出 `WorkProcess` 快照；每拍重建，不缓存。
- 映射规则按 03 §二：需求 id → `wp:<scope>`；一子卡 = 一 workTask；需求级阶段不映射；DAG 不映射（`nextReady` 折进事实）。
- 错误语义：输入缺必备字段（如无 requirementId）→ 抛 `REQBOARD_INVALID_INPUT`（复用既有码，不新增）。

## 2. 写回适配（pm 组合根，serves: FR-5, FR-6）

- 驱动器决策出的写动词**逐一对表**到 pm 用例（03 §三"写动词"行）：`createProcess/defineStages/startStage/closeStage/createTask/pauseTask/resumeTask/blockTask/completeTask/closeProcess` 等 → `AdvanceChain.advanceRequirement`、`ExecuteTask`、`Decompose`、任务状态推进等。
- 铁律：**写回只经 pm 用例，不直写 pm 存储**；不一致即对账告警（绝不静默）。
- 适配层落点：替换 `pm/src/adapters/goal-round-lifecycle.ts` / `goal-round-ports.ts`（同槽位换血）。

## 3. 服务面消费（serves: FR-5, FR-6）

- pm 运行时对 workprocess 领域值的读取只经 `ctx.workprocess` 服务与 `work/changed` 事件（B1 服务面语义）。
- 回合账：`roundsStarted` / `taskRounds` / `observeRound` / `effectiveCapOf` 不改，落 workprocess 存储域。
- 内存闸改耐久：`stagePlanAsked` / `humanAskAsked` 改读耐久记号 `asked`（03 §三）。

## 4. 工具面 / 命令面（serves: FR-6）

- `reqboard_task_run`：**保留**，语义收窄为"起链入口"（调用即写 `autoRun=true` 起链；后续拍由驱动器推进）。返回形状不变，描述文案更新。
- 六个 `*_workstage` / `*_worktask` 工具：随 `tool-workprocess` 装载进入工具面（宿主重启后可绑定）。
- `/work` 命令：随 `dsh-command-workprocess` 装载进入。

## 5. 装载接口（serves: FR-2, FR-3）

- `pm/cordis.patch.yml`：5 条 insert（id/name/config 照抄各包自带 patch；`blockedAfterRounds` 驱动器与工具面同值 = 3；`tick/drive/defaultMaxRounds=20/close=auto/disarmOnResume` 照抄 WP 现值，01-facts §1.5）。
- `pm/package.json` dependencies 增四包 `workspace:*`；`pm/tsdown.config.mjs` `WORKSPACE_PACKAGES` 增四条正则。
- 错误语义：`dsh.bundle.patch` 指向文件读不到 ⇒ 宿主整个跳过该 bundle（01-facts §1.5）——patch 五行的 id/name 错一个字即静默不装，验收必须靠 `composeEntries` 复现读数兜底（见 test-cases.md）。
