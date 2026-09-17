# REQ-47939a reqboard 分层重构：DDD 用例层拆分 + 领域规则收敛

> 状态：需求分析（brainstorming）· 窗口 w-41e7e4cd · 立据：用户 2026-09-17
> 分节确认：§1 问题定义 / §2 目标与范围 / §3 方案与验收 三节均经用户弹框确认（2026-09-17）
> "我发现实现好多代码写了几千行，这个应该通过设计模式或者 ddd 方式优化了"
> 全部数字为 2026-09-17 实测（wc -l / grep -c 于仓库工作区，非估算）。

## 1. 问题定义

插件 `packages/pages/dsh-pmboard` 共 **15,413 行**（host 9,006 + client 6,407）。六条债务：

| # | 债务 | 证据（实测） |
|---|------|--------------|
| D1 | **单文件垄断** | `host/agent-tools.ts` **2,946 行** = 13 个工具壳 + **98** 处拒绝分支 + **20** 处账本写入（`store.mutate`）+ **5** 处 fs 落盘（writeFileSync/mkdirSync/readdirSync），四类关注点同处一文件 |
| D2 | **规则散布** | 同一条状态机规则在四处各实现一遍：agent-tools（move/decompose）、routes.ts（:285 `:347 :355`）、rollup.ts、artifact-gates.ts |
| D3 | **用例不可复用** | HTTP 路由（`host/routes.ts` 1,074 行）无法调用工具层用例，只能重写逻辑；工具层也无法复用路由侧校验 |
| D4 | **规则无法独立单测** | 35 个测试文件 473 用例，全部走 `defineXxxTool(deps).execute()`；测"验收未过项如何生成返工任务"要造整个 deps + store + trace，领域规则没有独立可测入口 |
| D5 | **客户端同样膨胀** | `view.ts` 2,579 + `styles.ts` 1,886 + `stage-panel.ts` 662 + `board-mount.ts` 627，渲染/状态/样式耦合 |
| D6 | **仓库既有资产未被复用** | `@pi-investment/core-tool`（BaseTool 三段式 + `toDSHToolDefinition()`）、`packages/intelligence` 的 domain/services/adapters 先例、`docs/standards/tool-development.md` 均已存在，本插件却各自造轮子 |

**根因（一句话）**：领域规则没有独立归属地，于是只能跟着调用者长——第一个调用者把规则写在工具里，第二个调用者（HTTP）只好再写一遍。

**方法**：领域规则下沉 domain（纯、可单测）→ 用例进 application（只依赖端口）→ 工具壳与 HTTP 都退化成薄适配层。

## 2. 目标与非目标

### 2.1 目标

- **G1 规则单点化**：状态机、人工闸门、rollup 三条推进规则、done 凭证门、验收单规则全部下沉 domain——同一条规则全仓只有一处实现。
- **G2 用例可复用**：所有状态变更走 application 用例；工具壳与 HTTP 路由都变薄适配层，将来加第三个通道（CLI/看板按钮）不必重写逻辑。
- **G3 可独立单测**：domain 纯函数与用例能在不搭 store/ctx 的前提下测；把不变量逐条写成断言（见 §5）。
- **G4 尺寸约束**：宿主单文件 ≤400 行；工具一目录一文件（`XxxTool.ts` + `prompt.ts` + `index.ts`）。
- **G5 复用既有资产**：BaseTool 三段式（core-tool）、intelligence 的四层目录形状、`standards/tool-development.md` 硬约束。
- **G6 工具面收窄**：13 → 9（清单见 §4.3）。

### 2.2 非目标（明确不做，防止范围蔓延）

- **N1** 不改阶段方法论与流程语义——`stage-prompts.ts` / `docs/architecture/workflow-stages.md` 只改工具名引用，不改六要素与纪律内容。
- **N2** 不改客户端视觉与交互——`view.ts` 只做机械拆分，行为不变。
- **N3** 不新增功能、不动看板信息架构。
- **N4** 不引入新依赖（core-tool 已在仓内）。
- **N5** 不做多需求并发/多租户架构改造。

## 3. 范围与分期

| 期 | 内容 | 可独立交付 |
|----|------|-----------|
| **P0** | 宿主四层：domain + application + adapters + tools 拆分；routes 改薄；账本 v4→v5 迁移（含存量无损校验）；不变量测试 | 是 |
| **P1** | 客户端拆分：view.ts 2,579 → 按视图区分片；styles.ts 1,886 → 分层样式。纯机械 | 是（依赖 P0 的类型边界） |
| **P2** | 收尾：文档演进（workflow-stages / RFC 014 / TOOLS_INVENTORY / glossary）、旧路径删除、死代码清理 | 是 |

**迁移范围（用户未勾选"零迁移底线"，按需要求迁移执行）**：现账本 `schemaVersion=4`、`revision=870`、34 条需求 / 84 个任务 / 2 条待归类 / 736 KB。迁移须保证存量数据无损（口径见 §6）。

## 4. 方案

### 4.1 目标目录结构（方案 1：同插件四层 + 用例层）

```
src/
  domain/                      纯领域：零 fs / 零 ctx / 零网络 / 零 store
    requirement/RequirementStatus.ts   状态枚举 + 合法转移表（AGENT_TRANSITIONS / HUMAN_GATES）
    requirement/Requirement.ts         实体不变量守卫
    task/TaskStatus.ts  task/Task.ts
    task/Acceptability.ts              acceptance 可证伪校验（VACUOUS_ACCEPTANCE / VERIFIABLE_ANCHOR）
    workflow/RollupSpec.ts             三条推进规则 R1/R2/R3（纯函数：台账快照 → 推进决策）
    workflow/GateSpec.ts               人工闸门规约
    workflow/DoneEvidenceSpec.ts       done 凭证门规约
    workflow/AcceptanceSheetSpec.ts    验收单生成 / 逐项裁决 / 返工任务生成
    workflow/DocSyncSpec.ts            文档同步（change_note）规约
    artifact/ArtifactSpec.ts           产物分类 + 归档文档清单规则（ARCHIVE_DOC_RULES）
  application/                 用例：只依赖端口，不碰 fs/ctx
    ports.ts                   ReqboardRepository / DocRepository / Clock / IdFactory / SessionProbe
    use-cases/CreateRequirement.ts  MoveRequirement.ts  Decompose.ts
    use-cases/MoveTask.ts  ReportTask.ts
    use-cases/SubmitArtifact.ts        kind 分发到 4 个内部用例（不写成一个大 if）
    use-cases/ConfirmArtifact.ts  AskConfirm.ts  AcceptSheet.ts
  adapters/
    JsonLedgerRepository.ts    ← 现 store.ts
    FileDocRepository.ts       ← 现 agent-tools 内嵌 fs 落盘 + sync-artifacts.ts
    SystemClock.ts  IdFactory.ts
    SessionProbeAdapter.ts     ← 现 capture-hook 的 toolTrace / recentUserMsgs
  tools/<Name>Tool/{XxxTool.ts, prompt.ts, index.ts}     三段式薄壳
  http/routes.ts + http/routers/*.ts                     只做协议转换
  shared/protocol.ts           对外契约（HTTP + client 共享类型），位置不变
  client/                      P1 拆分
```

### 4.2 规则归属表（D2 的收敛映射）

| 现位置 | 规则 | 迁往 |
|--------|------|------|
| `agent-tools.ts` defineMoveTool | 状态机合法转移 + 人工闸门 | `domain/requirement/RequirementStatus.ts` + `workflow/GateSpec.ts` |
| `agent-tools.ts` defineDecomposeTool | 幂等守卫 / 前向引用 DAG / 薄卡拒绝 | `workflow/RollupSpec.ts` + `task/Acceptability.ts` |
| `agent-tools.ts` assertDoneEvidence | done 凭证门 | `workflow/DoneEvidenceSpec.ts` |
| `agent-tools.ts` accept_sheet | 验收单生成 / 逐项裁决 / 返工 | `workflow/AcceptanceSheetSpec.ts` |
| `agent-tools.ts` 4 个 submit | 产物闸门 + 文档同步 | `workflow/DocSyncSpec.ts` + `artifact/ArtifactSpec.ts` |
| `routes.ts` :285/:347/:355 | 状态前置校验（重复实现） | 删除，改调 application 用例 |
| `rollup.ts` / `artifact-gates.ts` | 推进 + 产物闸门 | 分别并入 `workflow/RollupSpec.ts` / `artifact/ArtifactSpec.ts` |

### 4.3 工具收敛清单（13 → 9）

- **4 个提交工具合一** → `reqboard_submit(kind: requirement\|plan\|verification\|archive)`。壳合并，内里仍是 4 个独立用例，**禁止写成一个大 if**。
- **`confirm_artifact` 并入 `reqboard_ask_confirm`**（弹框落章只剩一条路）。
- 保留：`create` / `status` / `move` / `decompose` / `task_move` / `task_report` / `accept_sheet`。
- 收敛后 9 个：`reqboard_create`、`reqboard_status`、`reqboard_move`、`reqboard_decompose`、`reqboard_task_move`、`reqboard_task_report`、`reqboard_submit`、`reqboard_ask_confirm`、`reqboard_accept_sheet`。

**已知代价（诚实标注）**：合并会削弱模型的"何时用哪个工具"发现性——4 个工具各有一条精准 description，合并后靠 `kind` 参数区分；所有阶段提示词与文档里的工具名要同步改。**可退回档**：若实施中发现发现性下降导致误用，退回"只合并 4 个 submit、保留 confirm_artifact 独立"的 13→11 保守档（见 §9 D-4）。

## 5. 不变量清单（验收的行为基准）

| ID | 不变量 | 现实现位置 |
|----|--------|-----------|
| INV-1 | 只有 AGENT_TRANSITIONS 允许的转移可执行；cancel/归档/取消任务等人工闸门对 agent 一律拒绝 | agent-tools defineMoveTool / routes |
| INV-2 | 每条不变量在 domain 只有一处实现；适配层（tools/ + http/）不得出现状态字面量比较 | 新约束（可机械检查） |
| INV-3 | decompose 对已拆分需求拒绝（幂等）；同 kind 产物重复登记幂等命中 | agent-tools :696 守卫 |
| INV-4 | done 凭证门：无 task_report / 窗口无真实工具动作 / 60s 连环关闭 / 客户端未构建 → 拒绝 | assertDoneEvidence |
| INV-5 | rollup：任务全 done → 自动 accepting；R1/R2/R3 三条推进规则顺序与结果不变 | rollup.ts |
| INV-6 | 验收单：每任务验收标准 + 需求级标准逐项；未过项生成返工任务并打回 implementing；v2 续验只含未过项 | accept_sheet / verdicts.ts |
| INV-7 | 产物：REQ 目录落盘自动登记；task_report files_changed 上浮；evidence 路径存在性；archive 漏登警告 | sync-artifacts / agent-tools |
| INV-8 | 迁移无损：v4→v5 后逐字段等价（除显式重命名字段） | 新增 |

## 6. 迁移策略

1. 迁移前自动备份（`dsh-reqboard.json.bak-<ts>`），dry-run 报告变更条数；
2. 读写双向兼容：`schemaVersion=4` 旧账本可读，首次写盘时升级到 5；
3. 校验脚本输出"迁移前后逐字段 diff"，**除显式重命名字段外 diff 必须为 0**；输出摘要落 `docs/requirements/REQ-47939a/`；
4. 失败即回滚（还原备份），迁移脚本幂等可重跑。

## 7. 验收标准（可证伪）

| # | 验收标准 | 判定方式 |
|---|----------|----------|
| A1 | INV-1..8 每条有对应测试文件与用例，全量 `npx vitest run` 全绿 | 命令 + 输出摘要 |
| A2 | 宿主单文件 ≤400 行；`host/agent-tools.ts` 不再存在 | `wc -l` 输出 |
| A3 | 适配层 grep 不到状态字面量比较（`status === '`），状态判断只出现在 domain/ | grep 输出为空 |
| A4 | 迁移无损：diff 报告为 0（除重命名字段） | 校验脚本输出 |
| A5 | 9 个工具 schema 全过 `tests/plugin-schema.smoke.test.ts`；HTTP 响应体与 protocol.ts 一致 | 测试输出 |
| A6 | `pnpm build:client` 通过 + verify-client-build 哨兵通过 + 页面功能回归清单逐项确认 | 命令 + 人工逐项 |
| A7 | 重放 3 个已归档需求（REQ-2e9473 / REQ-6f39b5 / REQ-9f4a44）的关键操作序列，结果与新实现一致 | 重放脚本 + 对比输出 |

## 8. 风险与缓解

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 473 个既有测试多为实现细节测试，大改后需重写 | 先补不变量层行为测试，再改实现；按"行为/实现"给既有测试分类，行为测试必须全绿，实现测试可重写但需覆盖同等断言 |
| R2 | fs 副作用从工具壳移入 adapters 时漏掉幂等/防重 | adapters 单测 + 迁移演练（备份→dry-run→校验→回滚） |
| R3 | 工具合并削弱发现性 | description 覆盖 4 个 kind 的用法与反例；阶段提示词同步；保留 13→11 退回档 |
| R4 | 一次性大改难以 review、难定位回归 | strangler-fig：新层与旧实现并存，逐用例切换，每步跑全量测试；P0 内拆 6 个批次，每批可回退 |
| R5 | 迁移损坏存量数据 | 自动备份 + dry-run + 逐字段校验 + 失败回滚 + 幂等重跑 |
| R6 | 多会话/多窗口同时使用看板，重构期间服务中断 | 改动在 worktree 隔离；真机验证窗口最小化；台账写入串行（store 已 atomic write） |
| R7 | profile 符号链接指向 worktree 才能真机验证（源码经 symlink 加载） | 实施阶段用 `relink-profile.py` 切换链接目标，验证后切回；该步骤在拆分阶段写成具体任务卡 |

## 9. 本阶段决策记录

| # | 决策 | 依据 |
|---|------|------|
| D-1 | 成功标准 = **C 档：允许破坏性变更**（非严格等价重构） | 用户弹框裁定（2026-09-17） |
| D-2 | 破坏面全部放开：工具集重划 / 账本数据模型 / 客户端契约 / 阶段提示词与文档；**未勾选"零迁移底线"→ 需写迁移并验证存量无损** | 用户弹框裁定（2026-09-17） |
| D-3 | 分层方案 = **方案 1 同插件四层 + 用例层**（对照方案 2 独立包 / 方案 3 文件级拆用例） | 用户弹框裁定（2026-09-17） |
| D-4 | 工具收敛取 **13 → 9** 充分档 | 用户弹框确认（2026-09-17）；**可退回 13→11 保守档**（只影响 2 个壳，不动分层） |
| D-5 | P0/P1/P2 三期**全部纳入本需求**（不拆成多个需求），三期各自独立可交付 | 用户弹框确认（2026-09-17） |
| D-6 | 依赖方向单向向内：domain 不得 import 外层；application 只依赖 ports.ts；适配层承载 fs/ctx | 随 §3 一并确认（2026-09-17） |

## 10. 本阶段文档自查（提交前逐项过）

| 检查项 | 结果 |
|--------|------|
| 占位符（TBD/待定/XXX/"稍后补"） | 无 |
| 内部矛盾 | 已核：D-1（允许破坏性变更）与 §7 A5（协议一致性）不冲突——A5 要求的是"改后一致"，不是"不改" |
| 模糊表述 | 已核：G4 的"≤400 行"、INV-2 的"grep 不到 status 字面量"、A4 的"diff 为 0（除重命名字段）"均为可机械判定口径 |
| 范围蔓延 | 已核：N1-N5 显式排除阶段方法论、客户端行为、新功能、新依赖、多租户；P1 客户端拆分限定"纯机械" |
| 数据来源可核验（R-013） | 全部行数/计数为 2026-09-17 仓库实测；账本口径 `schemaVersion=4 / revision=870 / 34 需求 / 84 任务 / 2 待归类 / 736KB` |
| 未决项是否显式标注 | 是：D-4 的 13→11 退回档、R7 的 worktree 链接切换均已标注为实现期可调整项 |

## 11. 下一步

进入 planning（技术设计）阶段：产出 `design/architecture.md`（分层与依赖方向）、`design/domain-model.md`（实体/值对象/规约签名）、`design/migration.md`（账本 v5 结构与迁移脚本设计）、`design/test-cases.md`（不变量 → 用例矩阵），并提交实施计划请人批准。
