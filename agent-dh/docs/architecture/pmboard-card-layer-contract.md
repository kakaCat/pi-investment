# 项目看板「卡片层」契约方案

> 主题：solo/chain 意图声明 · 泳道列推导 · DAG 折叠到卡片层 · 子卡链再生成
> 状态：**方案 + 实施（t1–t8 已落，未提交）**——代码改动与验收证据见 §6；仅 doc 卡默认可选项（§7-1）待拍板；部署（build + 重启）未执行
> 数据时点：2026-09-28 全量履约扫描（`docs/requirements/*/queue.json`，54 个队列 / 711 张卡）

## 0. 一句话

**把「卡片层」当成一等公民**：一张卡有**意图**（solo 单卡 / chain 带链），子卡链是卡的**内部流水线**而不是平级任务；台账、泳道、DAG、执行指引四个观测面统一按这条口径说话。

## 1. 问题：四处表现、一个根因

| # | 表现 | 实测证据（2026-09-28） |
|---|---|---|
| D1 | **泳道三列结构性为空**：联调中 / 测试中 / 待复核永远没有卡 | `renderSwimlane` 只取 `parentId===undefined` 且按 `t.status` 分列；而父卡状态机中段无出边（`PARENT_TRANSITIONS` 对 integrating/testing/in_review 为空）、子卡又被排除出列（只作卡底进度条）。全量 711 张卡落在三态的 **0 张**，同期 `stageKind=integrate\|test` 子卡各 49 张且全部 done |
| D2 | **DAG 混两个抽象层**：子卡与父卡同为节点 | `REQ-260924213231-b1c4`：65 节点 / 12 层，其中 52 个是子卡（80%），第 10–12 层全是子卡；折叠到卡片层 = 13 张顶层卡 / 9 层 |
| D3 | **执行指引教非法状态** | `capture-section.ts:143-146/205` 仍教 `to:'integrating'→'testing'→'in_review'`；父卡/子卡照做会被 `MoveTask` 判 `invalid_transition`（只有存量卡可走） |
| D4 | **意图不可辨 + 无再生成入口** | parent/legacy 由「有没有子卡」推导（`MoveTask.ts:54`）；契约无「不需子卡」声明（`validateExplicitStages` 拒空数组、模板最少 1 段）；`expandSubtasks` 只在开工那次触发且被 `req.autoRun` 门住（`MoveTask.ts:148`）。503 张顶层卡仅 **53 张（11%）**有链；43/54 需求 `autoRun=false`；doc 卡 36 张里 33 张无链、3 张吃通用 4 段、**0 张**走 doc 模板；85 条需求 **0 条** `category=doc` |

根因一句话：**「卡片层」与「子卡链层」两个抽象层在台账与观测面没有统一口径**——判定靠结果（有没有子卡）而不是意图（该不该有），于是"不需子卡"和"需要但未生成"长得一模一样。

## 2. 新思路

1. **意图显式化**：卡声明自己要 solo 还是 chain，系统不再靠"有没有子卡"反推。
2. **链是内部流水线**：链的阶段（dev→integrate→review→test）不是可独立调度的任务，不该作为 DAG 平级节点、也不该作为泳道列的直接依据；视图要展示的是**卡走到哪一步**。
3. **视图说人话**：泳道列 = 卡所处**环节**；DAG = **父卡**依赖图 + 卡底链进度；缺链与 solo 必须**视觉可分**。
4. **写路径补能力**：给"意图=chain 但链没生成"的卡一个**再生成（补链）**入口，而不是让人重跑开工。
5. **历史不追溯**：存量大面积无链是历史事实，默认按 solo 处理，不做批量生链。

## 3. 契约设计

### 3.1 声明层：`stages` 的空数组 = solo

| 取值 | 语义 | 落链行为 |
|---|---|---|
| `stages: []` | **本卡不落子卡链（solo）** | `expandSubtasks` 返回空集，永不生链 |
| `stages` 缺省 | 未指定 → 按 `phase → side → 需求分类` 映射（chain 默认） | 开工时懒展开 |
| `stages: [..]` | 显式段序（逃生舱口，受控枚举 + 去重） | 按声明落链 |

关键点：`undefined` 与 `[]` **必须走不同分支**。改动点：

- `src/domain/task/SubtaskTemplate.ts`：`validateExplicitStages` 接受空数组（原「stages 不得为空数组」改为合法返回 `{ok:true,value:[]}`）。
- `src/application/internal/lazy-expand.ts`：`resolveSubtaskStages` 判据 `.length > 0` → `!== undefined`（旧判据把"明确不要链"当"没写"，静默改回默认 4 段）。
- 意图需**可见**：`StageTaskRef.stages`（`shared/protocol.ts`）+ 装配器投影（`QueryStageDetail.toStageTaskRef`）+ 客户端 `TaskRecord.stages`。装配器是**手工挑字段**的，子卡层曾因漏投影导致「35 张卡父卡=35 子卡=0」，这次的意图字段同样必须显式投影。

### 3.2 视图层 A：泳道列 = 卡所处环节（`laneOf`）

| 卡 | 列 |
|---|---|
| `todo` / `done` / `canceled` | 自身状态（canceled 无列，现状不变） |
| 无子卡（solo / 存量卡） | 自身状态（存量卡保留五段：integrating/testing/in_review 仍可显示） |
| chain 卡，链上第一个未完成子卡为 `dev` | 开发中 |
| …为 `integrate` | **联调中** |
| …为 `review` | **待复核** |
| …为 `test` | **测试中** |
| 链全绿而父卡未收尾 | 待复核（把卡住的卡浮出来） |
| 未知 stageKind（fix/regress/probe…） | 回落开发中 |

单一事实源：`laneOf` 与链条进度条共用 `alignKids` / `STAGE_ORDER`（`src/client/dag/progress-bar.ts`），避免两处口径分叉。两处渲染同时切换：`node-panel.renderSwimlane`、`stage-detail.buildTaskColumns`（后者同样是 6 列 + 只取顶层卡，是同款死列）。

### 3.3 视图层 B：DAG 折叠到卡片层（`collapseToCardLevel`）

- 节点集 = 顶层卡；**子卡不出现为节点**。
- **边重路由**：依赖里指向子卡 → 上提到其父卡；同一父卡内部链边折叠后成自环 → 丢弃；指向本队列外、画不出节点的悬空依赖 → 丢弃。
- **保留跨卡依赖**：实测 73 条（22 条指向父卡、51 条指向存量卡），它们才是排期语义。
- 两个渲染器共用同一函数：`node-panel.renderDag`（HTML 版）与 `dag-view`（Canvas 版）。
- 可选「展开子卡」开关（默认折叠）；钻取入口不变（点卡打开任务卡文档）。
- 收益实测：`REQ-260924213231-b1c4` 65 节点/12 层 → 13 卡/9 层。

### 3.4 视图层 C：「链未生成」徽标

触发条件（`chainMissing`）：**卡正在跑（`in_progress`）+ 没有子卡 + 未显式声明 `stages: []`**。

- 为什么限定 `in_progress`：todo 卡开工时才懒展开，"还没链"是正常态；done 的存量卡属历史，大面积打标只会变噪声。
- `stages: []` 的 solo 卡**永不打标**——这正是"不需子卡"与"需要但未生成"的分界线，也是本次困惑的直接解法。

### 3.5 写路径：再生成（补链）

**语义**：对指定父卡按 `resolveSubtaskStages` 重算应有段，**只补 `stageKind` 缺失的段**。

| 规则 | 内容 |
|---|---|
| 幂等 | 已有子卡（含 done）一律不动；再调一次不产生新卡 |
| 差集 | 应有段 − 已有段 = 待补；补出的新卡接在链尾，dependsOn 指向前一张 |
| solo | `stages: []` 的卡 **skip 并回执说明**（不静默跳过） |
| 安全默认 | `dry_run` **默认 true**（在 execute 内显式兜底，不靠 schema default——本仓铁律） |
| 审计 | 写台账须 `decision_audit` + 工具 reason |
| 与 autoRun 门的关系 | 显式再生成**不受** `req.autoRun` 限制（否则对 43 个非自动链需求无用） |
| 入口 | 新增工具 `reqboard_task_regenerate`（复用 `expandSubtasks`，不新写一套生成逻辑） |
| 配套诊断 | `reqboard_task_tree` 增加诊断字段：无链 chain 卡 / 半链缺段 / 悬空 parentId / 疑似可归组散卡 |

**不做**：换绑（把标题形如 `X·联调` 的平级散卡挂回父卡 X）。全量扫描显示此类异常当前为 **0**（悬空 parentId 0、有 stageKind 无 parentId 0、子卡名却无 parentId 0），故本期只做只读诊断清单，写路径留待出现真实样本再开。

### 3.6 文案层：执行指引按角色出边

`capture-section.ts` 当前无条件教三段（integrating→testing→in_review）。改为按角色：

| 角色 | 合法边（来自 `TaskStatus.ts`） | 指引措辞 |
|---|---|---|
| 父卡 / 子卡（有 kids 或自身是子卡） | `todo→in_progress→done` | 完成后 `to:'done'`；联调/测试由子卡链各阶段承载 |
| 存量卡（无 kids 且自身非子卡） | 五段 | 保留 integr→testing→in_review→done |

### 3.7 历史数据与 doc 卡默认

- **历史卡默认 solo，不追溯**：不批量生链（否则 503 张顶层卡可能一次性生出上千子卡，看板结构剧变）。
- **doc 卡默认**：实盘 36 张里 33 张就是无链单卡 → 建议**默认 solo**，需要链的显式声明。附带提醒：在制的 `stagesForPhase/stagesForSide` 解析一旦生效，autoRun 需求里的 doc 卡会从"无链"变成"2 段链（dev→review）"，即**改变文档工作的跑法**，需要显式决定。

## 4. 任务拆分与验收

| # | 任务 | 改动点 | 验收命令 |
|---|---|---|---|
| t1 | 声明层 solo 语义 | `domain/task/SubtaskTemplate.ts`、`application/internal/lazy-expand.ts`、`shared/protocol.ts`、`client/types.ts`、`application/query/QueryStageDetail.ts` | 单测：`stages:[]` → `resolveSubtaskStages` 返回 `[]`；`undefined` → 仍走映射 |
| t2 | 卡片层纯函数单一事实源 | `client/dag/progress-bar.ts`：`STAGE_LANE`/`laneOf`/`chainMissing`/`collapseToCardLevel` | 纯函数单测（映射表 + 边界 + 边重路由） |
| t3 | 泳道列切换 | `client/node-panel.ts`、`client/views/stage-detail.ts` | `renderNodePanel`：integrate 子卡在跑 → 卡落 `data-col="integrating"` 且不在 `in_progress` |
| t4 | DAG 折叠 + caption | `client/node-panel.ts`、`client/views/dag-view.ts` | 折叠后节点数 = 顶层卡数；跨卡依赖边保留 |
| t5 | 链未生成徽标 | 两处渲染 + `client/styles/*` | `in_progress` 且无链 → 有徽标；`stages:[]` → 无徽标 |
| t6 | 再生成（补链）能力 | 新 use-case + `tools/TaskRegenerateTool` + `tools/index.ts` + `src/index.ts` | 幂等：连调两次不增卡；solo 卡 → 回执 skip；`dry_run` 默认 true |
| t7 | 执行指引按角色出边 | `application/internal/capture-section.ts` | 注入文本断言（父卡/子卡只有 done 一条；存量卡保留三段） |
| t8 | 测试与构建核验 | — | `npx vitest run tests/…`；`pnpm build:client` + `grep -c '联调中' lib/client.js`；页面核验 |

发版路径（本仓铁律）：改的是 **client 半 + dist 包**，必须 `pnpm build:client`（tsdown + wrap-client + verify-client-build 三道门），再走 `agent-dh/scripts/restart-with-build.sh`；:13080 由 launchd 托管，**不要 kill**。

## 5. 风险与不做的事

- **列语义变化**：泳道列从"卡自身状态"变为"卡所处环节"，必须由 caption 与卡面 tooltip 说清（已写进 t3/t4 的 caption），否则会被读成"卡的状态是 integrating"。
- **不追溯历史**、**不批量生链**、**不做换绑写路径**（无真实样本）。
- **不动存量状态机**：solo 卡继续走 legacy 五段（含 done 证据门），本次不改 `TaskStatus` 转移表。
- 本方案不涉及投资域规则（R-001~R-020），不构成任何仓位/止损/信号分级依据。

## 6. 当前落地状态（诚实台账）

**已落（t1–t8 全部，均为未提交改动；`tsc --noEmit` 本次涉及文件 0 错误）**：

| # | 文件 | 改动 |
|---|---|---|
| t1 | `src/domain/task/SubtaskTemplate.ts` | `validateExplicitStages` 接受空数组（=solo）+ 3 处注释 |
| t1 | `src/application/internal/lazy-expand.ts` | 判据 `!== undefined`；抽出 `makeChild`（与补链共用）；新增 `chainDiagnosis` / `regenerateChain` |
| t1 | `src/shared/protocol.ts`、`src/client/types.ts` | `StageTaskRef.stages?`、`TaskRecord.stages?` |
| t1 | `src/application/query/QueryStageDetail.ts` | 装配器投影 `stages`（手工挑字段的经典漏项） |
| t2 | `src/client/dag/progress-bar.ts` | `STAGE_LANE` / `laneOf` / `chainMissing` / `collapseToCardLevel` |
| t3 | `src/client/node-panel.ts`、`src/client/views/stage-detail.ts` | 泳道列与任务五列都改 `laneOf`；链未生成优先于 [手动] 标 |
| t4 | `src/client/node-panel.ts`、`src/client/views/dag-view.ts` | HTML DAG 与 Canvas DAG 共用折叠；画布尺寸按顶层卡；标题/caption 改口径 |
| t5 | `src/client/styles/subtask.ts`、`src/client/styles/node-panel.ts` | `.dsh-pm-chain-missing` / `.dsh-pm-np-chain-missing` |
| t6 | `src/application/use-cases/RegenerateChain.ts`（新）、`src/tools/RegenerateTool/index.ts`（新）、`src/tools/index.ts`、`src/index.ts` | 工具 `reqboard_task_regenerate`：`dry_run` 默认 true；真写须 `task_id`+`reason`；只补缺失阶段；solo 跳过并回执；父卡 comment 留痕 |
| t7 | `src/application/internal/capture-section.ts` | 执行指引按角色出边（父卡/子卡只有 done；存量卡保留五段） |
| t8 | `tests/card-layer.test.ts`（新 13 例）、`tests/domain/subtask-template.test.ts`（1.4b 契约更新） | 见下方验收 |

**验收证据（2026-09-28 23:5x）**：

- `npx vitest run tests/card-layer.test.ts tests/domain/subtask-template.test.ts tests/node-panel.test.ts tests/stage-detail.test.ts` → **85 passed / 4 files**；另 `tests/regenerate-chain.test.ts`（新，9 例：solo 不落链 / 全量补 / 只补差集 / 已有子卡不动 / 幂等 / doc 卡仍 2 段）→ **9 passed**；
- 全量 `npx vitest run` → 2559 passed / 87 failed（36 files）：抽查 8 类失败全部落在**在制工作线**的改动面上（`boundSectionText` 三参签名漂移、decompose W7 语义、`task_card.acceptance`、看板 archived bar、Canvas DAG 替换后的 L0 断言、REQ id 格式、layer-boundary 的 node:fs、size-budget 超标文件清单），**无一条出自本次改动**；
- `pnpm build:client` → OK（`[verify-client] OK`，产物含「联调中」「链未生成」）；
- 宿主半编译核验用 `npx tsdown -c tsdown.config.mjs --out-dir /tmp/pmboard-host-check` **落地到临时目录**（因 `tsdown.config.mjs` 是 `clean: true`，直接 build 失败会清空 dist）→ OK，产物含 `reqboard_task_regenerate`；
- 尺寸：本次改动文件均 <400 行，但 `src/client/views/stage-detail.ts` 已 **387 行**（size-budget 门禁上限 400）——下次在该文件加逻辑前先拆。

**基线说明**：本批改动落在主工作区现有在制改动**之上**（`node-panel.ts`/`lazy-expand.ts` 等本就在 228 个未提交改动中）。若要撤回：**不要用 `git checkout`**（会连带抹掉在制工作线在这几个文件里的改动），需按上表逐条还原。

## 7. 待拍板

1. **doc 卡默认**：**仍未定**（本次未改任何映射表，文档卡行为零变化）。需你选：solo 单卡（合实盘 33/36）／保留 2 段链 `dev→review`。选了就改 `PHASE_STAGES.doc` / `SUBTASK_TEMPLATES.doc` 一处。
2. ~~改动基线~~ → **已定（2026-09-28 用户裁定）：继续在主工作区在制改动之上改**。
3. ~~t6 范围~~ → **已定：只做「补链 + 只读诊断」**；换绑留待出现真实样本再开。
4. ~~是否转正式需求~~ → **不做**（用户裁定：立项流程太慢）。

**剩余动作（部署面）**：宿主半尚未写入 `dist/`（本次只到临时目录核验）——要上线需 `pnpm build`（注意 `clean: true`，失败会清空 dist，构建后必须校验产物）＋ `agent-dh/scripts/restart-with-build.sh`（会重启 :13080，当前会话断线后自动续跑）。
