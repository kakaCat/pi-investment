# REQ-47939a 独立复核记录（发起窗口 w-41e7e4cd 逐卡验收）

> 本文件由**发起窗口**（REQ-47939a 的绑定窗口）撰写，不是执行窗口的自述。
> 每张卡在关闭前，由发起窗口**自己跑一遍卡面验收命令**并附证据；执行窗口的汇报只作参考。
> 与 `tasks/<id>.md` 的分工：那里是**执行者汇报**（做了什么），这里是**验收者复核**（我验证到了什么）。

## t1 t-07e4ff 立层边界门禁与端口骨架

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 卡面验收命令 | `npx vitest run tests/layer-boundary.test.ts` | **9/9 passed** |
| 门禁是否真能失败（故障注入） | 往 `src/domain/errors.ts` 注入 `import { readFileSync } from 'node:fs'` | 红：「domain/ 出现越界 import」 |
| 同上 | 把 `domainError` 改为使用 `Date.now()` | 红：「domain/ 出现非确定性来源」 |
| 还原后 | 重跑 | 9/9 绿（注入已还原） |
| 全量回归 | `npx vitest run` | 504 passed / 1 failed（基线项，非本次引入） |

## t2 t-e331f2 领域搬迁A：状态机 + 可证伪验收 + 产物规则

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 卡面验收命令 | `npx vitest run tests/domain tests/reqboard.test.ts` | **91 passed** |
| **单点实现（INV-2 核心）** | `grep -rn 'const REQ_TRANSITIONS' src/` | **1 处**，在 `src/domain/requirement/RequirementStatus.ts` |
| 同上 | 对 `TASK_TRANSITIONS` / `HUMAN_ONLY_REQ_TRANSITIONS` / `ARCHIVE_DOC_RULES` / `STAGE_ARTIFACT_REQUIREMENTS` 逐个 grep | 各 **1 处**，全部在 `src/domain/` |
| 层边界未破 | `npx vitest run tests/layer-boundary.test.ts` | 9/9 绿（domain 13 个文件零越界） |

## t3 t-a68851 领域搬迁B：rollup + done 凭证门 + 幂等 + 文档同步 + 里程碑

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 卡面验收命令 | `npx vitest run tests/domain tests/rollup.test.ts tests/task-output-and-evidence.test.ts` | **81 passed** |
| **纯度（domain 不碰时间/随机/I/O）** | `grep -rn 'node:fs\|Date.now()\|Math.random()' src/domain/` | **0 处** |
| 纯度断言存在 | `grep -c 'Object.freeze' tests/domain/rollup.test.ts` | 3 处（入参冻结后调用不抛，证无副作用） |
| 单点实现 | 对 `checkDoneEvidence` / `checkDecomposeIdempotency` / `applyDocSync` / `shouldRemindConfirm` 逐个 grep | 各 **1 处**定义，均在 `src/domain/` |

## t4 t-7cc481 领域搬迁C：验收单规约

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 卡面验收命令 | `npx vitest run tests/domain tests/verification-sheet.test.ts tests/verdicts-and-rework.test.ts` | **68 passed** |
| 单点实现 | `grep -rn 'export function buildSheet' src/` | **1 处**，在 `src/domain/workflow/AcceptanceSheetSpec.ts` |
| `applyVerdicts` 两处是否构成第二实现 | 读 `src/host/verdicts.ts` | **否**——host 侧 import domain 的 `applySheetVerdicts`，只加台账校验（需求/状态/版本）与落库副作用（任务 id、状态事件、评论）；规则仍单点 |
| **既有测试断言改写审查**（本卡改了两处既有断言） | `git diff -- tests/verification-sheet.test.ts tests/verdicts-and-rework.test.ts` | 改动**纯机械且未削弱**：`toBe('t-bbbbbb')` → `toEqual({kind:'task',taskId:'t-bbbbbb'})`（由字符串相等升级为整对象相等，更强）；`find(i => i.source === 'x')` → `find(i => i.source.kind==='task' && i.source.taskId==='x')`。断言条数未减少 |
| 续版语义实测 | 读 `AcceptanceSheetSpec.ts:81` | `prevFailed = items.filter(status==='failed')` → **续版只含 failed，pending 项不加**（与文档草案"pending+failed"不符，见下方待裁决） |

**裁决结果（2026-09-17，用户选"本轮顺带修"）→ 已修复**：

- 语义：返工续版 v2 = 上一版 **failed（未过项）+ pending（未裁决项）**；上一版**没有** failed 项时仍重新生成全新验收单（不进入续版）——后一条是修复时必须保住的既有语义，已加守卫用例。
- 实现：`AcceptanceSheetSpec.buildSheet` 的 `carried` 由"只 filter failed"改为"filter failed 或 pending"，顺序沿用上一版。
- 断言更新：`tests/domain/acceptance-sheet.test.ts`（续版用例 + 新增"仅 pending 不进续版"守卫）、`tests/verification-sheet.test.ts`（v2 sheet_items 1→2）。
- 回归：`npx vitest run tests/domain tests/verification-sheet.test.ts tests/verdicts-and-rework.test.ts tests/acceptance-criteria.test.ts` → **106 passed**。
- 为什么值得改：这是"逐项验收"这条人工门的**实效漏洞**——未裁决项若能随返工消失，人就可能在"从未验过"的状态下归档。

## t5 t-4bbbf2 适配器落地

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 卡面验收命令 | `npx vitest run tests/application/repository.test.ts tests/capture-hook.test.ts` | **40 passed** |
| 适配器齐备 | `ls src/adapters/` | 6 个：JsonLedgerRepository/FileDocRepository/SystemClock/RandomIdFactory/SessionProbeAdapter/UserQuestionsAdapter |
| 原子上写有实测断言的痕迹 | `grep -c 'tmp\|rename' tests/application/repository.test.ts` | 10 处（含"写后无 .tmp 残留"与"rename 失败时目标不被污染"的故障注入断言） |
| 尺寸 | `wc -l src/adapters/*.ts src/application/*.ts` | 新模块全部 ≤400 行 |
| 客户端构建门 | `pnpm build:client` + `verify-client-build.mjs` | 通过（因本批改了 src/client/stage-panel.ts） |
| 诚实标注 | subagent 自述 | 适配器端口**尚未切进工具调用链**（agent-tools 的私有认证/弹框逻辑仍在），是并存实现，切换属 t8 |

## t5 t-4bbbf2 适配器落地（复核见上表；本节为文件 mtime 锚点）

见上一节 t5 表格。


---

## t6 / t7 / t8（用例层 · 路由改薄 · 工具 13→9）—— 发起窗口复核

### 复核结论一览

| 项 | 命令 / 方式 | 结果 |
|----|------------|------|
| 全量回归 | `npx vitest run` | **611 passed / 1 failed**（唯一失败为基线项 `board-info-fixes`，失败数未从 1 变 2） |
| 插件 schema 冒烟 | 根 `tests/plugin-schema.smoke.test.ts` | 19 passed |
| 工具形状 | `ls -d src/tools/*/` | **恰好 9 个目录**，每个 `XxxTool.ts + prompt.ts + index.ts` |
| 契约扫描器是否空转 | **故障注入**：删掉 `StatusTool` 里被返回的 `bound` 声明 | 红：`defineStatusTool 的 return 含未声明字段：bound` → 证明 t8 改造后的**多文件扫描 + RESPONSE_SOURCES 映射确实覆盖 9 个新工具** |
| 结果 | 还原后 | 24 passed，无残留 diff |

### 🔴 复核中发现并修复：层边界门禁有洞（第 5 次"门禁失效而假绿"）

- **现象**：t7 自述"http/ 内 `status ===` 字面量已清零"属实，但 `src/http/` 整体仍有 **8 处 `status !== '...'`**，门禁**没报**。
- **根因**：门禁正则只匹配 `===`（`/status\s*===/` 与 `/===\s*'...'/`），**`!==` 一个都匹配不上**。同一文件内还有 25 处 `statusIs(x, 'accepting')` 这类写法——首版 `domain/status/Predicates.ts` 是**通用比较器**，只把运算符搬进 domain、规则仍在适配层，门禁的 ARG 规则当时也不存在。
- **修复**：① 门禁分三层口径（比较式任意算子 / 判定器实参 / **任何独立状态名字面量**，名单由 domain 的 `REQ_TRANSITIONS`/`TASK_TRANSITIONS` 键动态取，避免手抄名单漂移——我第一版探针手抄就漏了 `in_progress`）；② `Predicates.ts` 重写为**按意图命名**的判定（`isAccepting`/`isVerifiableStage`/`isUnfinishedTask`/`countDoneTasks`…），删除通用比较器（不给"绕过去"留口）；③ 转移目标与初始状态也收进 domain 常量（`INITIAL_REQ_STATUS`/`REWORK_REQ_STATUS`/`ACCEPTED_REQ_STATUS`/`CANCELED_REQ_STATUS`/`INITIAL_TASK_STATUS`），适配层不再决定"新需求从哪开始、返工回哪"。
- **故障注入实测**：往 `src/http/routers/shared.ts` 注入原洞形态 `r.status !== 'accepting'` → 门禁红；还原后 9/9 绿。
- **改动后**：全量仍 611 passed / 1 failed。

### 🟡 复核中确认的历史事故：subagent 自报覆盖了 `host/routes.ts`

- 它自报：误把工作区 1075 行的 `host/routes.ts` 覆盖成 shim，用 git HEAD 版（1074 行）恢复并重放 t4 的 union 适配。
- **我的独立核验**：用消息字面量账（`scripts/req47939a-lit-diff.mjs`）比对 `HEAD:src/host/routes.ts` 与 `src/http/`（递归）——**旧 60 条，新目录 60 条，旧有新无 = 0**。结合路由三件测试（`routes-rollup`/`reqboard`/`api-client`）全绿，判定**未丢用户可见内容**。

### 🟡 确认的偏离：未使用 core-tool 的 BaseTool（理由成立）

- 卡面要求用 `@pi-investment/core-tool` 的 BaseTool 三段式；实现保留 `defineTool` 直接构造，但落成三段式**文件形状**。
- **理由已核实**：`BaseTool.toDSHToolDefinition()` 的 `execute` 在失败时 `throw new Error(issue)`——**裸 Error，丢掉 `.code`**，与本仓 `Object.assign(new Error(msg), {code})` 的契约冲突（错误码是路由/测试/模型共同依赖的契约）。
- **判定：接受该偏离**。真正的修法是让 BaseTool 透传 `code`，但那属于 core-tool 的改动，超出本需求范围；已记为后续项。

### 端口注入落实情况（此前文档措辞已按实测改正）

用例里走注入端口 `deps.ids` **28 处**；残留直接全局 ID 生成 **2 处**、直接 `Date.now()` **1 处**——端口化基本落地，残留 3 处列入 t9 收口。

### 仍未拆除的并存实现（t9 范围，已在卡面预期内）

`host/{rollup,verdicts,artifact-gates,sync-artifacts,capture}.ts` 与 `application/internal/` 暂时并行（`index.ts` 仍用 `host/rollup`+`capture`；`http/routers/stages` 用 `host/sync-artifacts`）；三处路由前置守卫按"零行为变更"保留（其文案/错误码是可见行为），但已改为经 domain 判定。

## t9 / t10（删 host/ 并存实现 · 尺寸门禁 · 迁移收尾）—— 发起窗口复核

### 复核结论

| 项 | 命令 / 方式 | 结果 |
|----|------------|------|
| 全量回归 | `npx vitest run` | **616 passed / 1 failed**（唯一失败为基线项；失败数未从 1 变 2） |
| 插件 schema 冒烟 | 根 `plugin-schema.smoke.test.ts` | 19 passed |
| `src/host/` 是否删净 | `[ -d src/host ]` | **NO**（整目录已删，`agent-tools.ts` 亦不存在） |
| 尺寸门禁 | `tests/size-budget.test.ts` | 5 passed |
| **尺寸门禁能否真红** | 故障注入：造 `src/domain/__size_probe.ts`（402 行） | 红：「超标文件（未在白名单内）」；删除后 5 passed |
| 体积白名单设计 | 读 `tests/size-budget.test.ts` | 5 条且**限死在 client/ 与 shared/protocol.ts**、逐条带理由、**必须当前仍超限**（t11/t12 拆完自动变红 → 防白名单只增不减）。这个设计比卡面要求更严，予以保留 |
| 真实台账未被迁移 | 读 `.dsh-data/dsh-reqboard.json` | `schemaVersion=4`、34/97 不变 → **未迁移** ✓（md5 与我先前测得不同是我自己 move 任务把 revision 926→927 所致，非它改动） |
| `REQBOARD_SCHEMA_VERSION` | grep + 读 `JsonLedgerRepository.load():103` | 已 4→5；且确认 `load()` 用该常量为解析结果重建 schemaVersion——**若不升常量，v5 文件会被报成 4 并在下次写盘回退，迁移成果被静默抹掉**。子代理这个判断正确且必要 |

### 关键核验：删 `host/` 后**用户可见文本零丢失**

用消息字面量账**逐模块**比对 `HEAD:src/host/<file>` 与新 `src/`（递归），13 个模块结果：

| 模块 | 旧有新无 | 判读 |
|------|---------|------|
| artifact-gates / capture-hook / capture / routes / stage-detail / stage-prompts / store / sync-artifacts / verdicts | **0** | ✓ 逐字保留 |
| **rollup.ts** | 2 | 经查**文本仍在**（`domain/workflow/RollupSpec.ts:139/156`，仅由模板串改成字符串拼接）→ 工具误报，非丢失 |
| classifier.ts / session-sync.ts | 25 / 10 | **已删的退役机制**（M2 自动分类）的文案 → 属有意删除 |
| agent-tools.ts | 51 | t8 的工具 description 重写（卡面要求"覆盖 4 个 kind 的用法与反例"）→ 属有意改写，逐条归因均落在工具壳，**0 条来自 t9 搬迁的 12 个模块** |

### 复核中处置的问题：迁移变换的**第二份实现**（INV-2）

- 现状：`src/application/use-cases/MigrateLedger.ts`（175 行，含 `buildV5Ledger`/`migrateLedger`）与 `scripts/migrate-ledger.ts` 的 `migrate()` 是**同一变换的两份实现**；前者仅被自己的测试引用，src 内**零调用**。
- 背景：t6 的卡注释写明本意是"t10 直接复用"，但 t10 按 D-8 走 CLI 直做，于是留下两份。
- **处置：删除该用例实现**（连同其 describe 块，位置留下说明注释）。保留**被端到端实测覆盖**的脚本实现（`tests/migration.test.ts` 9 passed + 真实副本 dry-run/apply/verify/幂等/损坏保护/回滚）。理由：同一变换只能有一处实现；把 CLI 改成依赖用例需要改动已实测通过的路径与多处断言，收益仅是形式统一。
- **对 t6 的修正**：t6 卡面的"12 个用例"实际为 **11 个**；从 175 行降到 0。已在此留痕，非静默。
- 删除后：`tests/application` + `tests/migration.test.ts` → 43 passed；全量 **616 passed / 1 failed**。

### 死代码删除的例外（已按四条要求执行）

删除 `classifier.ts`/`session-sync.ts` 的退役机制（`SessionSyncService`/`classifySession*`/`extractExplicitId` 等）连带删除 `tests/reqboard.test.ts` 的 **11 个用例**（4 个 describe），并以 **13 个新用例**覆盖 3 个活函数（`adapters/SessionMessageFilter.ts`）。净变化 **−11 +18 = +7**。经我复核：被删 11 例断言的确实是**已退役机制**，没有一例断言那 3 个活函数 → "活行为重建"不欠账。**这是对"删死代码"的例外，不属于断言削弱**，已在任务汇报与本节留痕。

## t13（文档演进与死代码清理）—— 发起窗口执行与复核

> 本卡由**发起窗口**执行（doc 类，纯 docs/，与 t11/t12 的 src 工作零重叠，故在等待期完成）。

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 卡面验收：wiki 探针（**须从仓库根跑**） | `cd <repo-root> && python3 agent-dh/scripts/wiki_probe.py` | **现行页死链 0 条 / 孤儿页 0 个** ✓；`exit=1` 来自别类（历史档案缺 front-matter、待提炼队列 75 篇），**与死链/孤儿无关**（判读口径已写进 `docs/standards/testing.md`） |
| 卡面验收：9 个收敛后工具名 | grep `docs/architecture/workflow-stages.md` | 9 个全出现（create 2 / status 1 / move 1 / decompose 2 / task_move 1 / task_report 2 / submit(kind= 3 / ask_confirm 4 / accept_sheet 2） |
| 卡面验收：不再把 confirm_artifact 列为独立入口 | grep `reqboard_confirm_artifact` | **0 次** ✓ |
| 文档演进 | 已落地 | `workflow-stages.md` 新增「工具面（13→9）」章节 + 同步现行引用；`rfcs/014` 新增 **§15**（分层 + 收敛 + 四条实测经验）；`glossary.md` 新增 4 条术语（四层分层 / 端口·用例 / 机械门禁 / 续版验收） |
| `TOOLS_INVENTORY.md` | grep | 该页只登记投资工具，**本无 reqboard 条目 → 无需更新**（在此显式记录，避免被当成漏做） |
| 死代码清理 | 全仓扫描（同时认 .ts/.js 后缀，含 scripts/tests 引用方） | **无死文件** ✓（首扫用错后缀模式产生 13 个假阳性，修正后复扫为空；client 文件用 `.ts` 后缀 import、迁移脚本引用 `domain/legacy/LegacyStatus.ts` 均属实） |
| 文档索引一致性 | `docs_index.py --check` | OK（**须从仓库根跑、且连跑两次才收敛**——该陷阱已写进规范页） |

**边界原则（本次显式遵守）**：`docs/work-logs/**` 与 RFC 的历史叙述章节是**当时事实的记录**，只增不改——故只在 living 文档更新"现行 API 表述"，并在 RFC 用**新增一节**记录收敛，不回溯改写旧章节。

## t11 / t12（客户端 view.ts 与 styles.ts 机械拆分）—— 发起窗口复核

| 复核项 | 命令 / 方式 | 结果 |
|--------|------------|------|
| 全量回归 | `npx vitest run` | **616 passed / 1 failed**（基线项；失败数未变 2） |
| 客户端三件 | `tests/client-view + stage-panel + card-face` | 113 passed（54/44/15） |
| **导出集合是否守恒** | 独立脚本：`git show HEAD:src/client/view.ts` 的顶层 export（14 value + 4 type）vs 新 barrel+views+render 的并集 | **缺失 value 0 / type 0** ✓（新侧 89 个是因为拆分把原本私有的 helper 转为导出，属预期不丢） |
| **CSS 是否逐字节不变** | 独立脚本：从 `/tmp/req47939a-t12-backup/styles.ts` 提取原 CSS 模板（**89,677 字符**）vs 5 个分片按 barrel 顺序（base→detail→files→board→panel）拼接 | **逐字节一致 YES** ✓ |
| 尺寸 | `wc -l` 全量 | 无任何分片 >400；view.ts 16 行 / styles.ts 26 行（降为 barrel） |
| 白名单 | 读 `tests/size-budget.test.ts` | `client/view.ts`、`client/styles.ts` 两条**已按门禁要求删除** ✓；stage-panel(663)/board-mount(627)/shared/protocol.ts(1114) 保留且理由已改写 |
| 构建门 | `pnpm build:client && verify-client-build.mjs` | exit 0；哨兵 OK；`lib/client.js` 新于 src 最新改动 |
| 它声称的"3 个死 import 未搬" | 独立核对 `HEAD:view.ts` | 属实：`renderStagePanel`/`getStageLabel` 各仅 import 行出现 1 次；`STAGE_LABELS` 第 2 处出现是**注释**（line 25）→ 三个确为死 import，删之无行为影响 |

**偏离（已接受）**：卡面写 view.ts → 6 个 views 分片 + dom-utils；实际**多出 2 个分片**（`views/stage-nodes-quality.ts`、`views/stage-nodes-doc.ts`）——原因是节点专属内容渲染器约 950 行，在"每文件 ≤400 行"的门禁下 7 个文件装不下 2579 行；卡面点名的 6 个文件名**全部保留**。另 styles 分片取"连续区段"而非按主题重排（重排会改 CSS 级联行为），这是**正确**的取舍。
**未拆完的**：`client/stage-panel.ts`(663)、`client/board-mount.ts`(627)、`shared/protocol.ts`(1114) 仍在白名单内（理由已写清，属后续卡/独立卡）。

## t9 前置（验证仪器：用户可见消息文本账）

`agent-dh/scripts/req47939a-message-inventory.mjs` —— 抽取旧 `host/agent-tools.ts` 与**新分层**（application + domain + adapters）两侧的单引号/双引号/模板字符串中文**字面量**做集合比对。

- **为什么要趁现在做**：t9 会删除 `host/agent-tools.ts`。旧实现还在时它是"行为等价"的**判据**（搬迁是否逐字保住了用户可见文本）；删掉之后再想核验就没有基准了。
- **基线（2026-09-17，t6 期间）**：旧 374 条 / 新分层 301 条 / **旧有新无 153 条**。这 153 条绝大多数是**工具 description 与参数说明**（如 `board = 弹框不可用…`、`evidence=证据清单…`）——它们属于 **t8 的工具壳**，尚未搬迁，故缺失属预期。
- **用法与判读**：t8/t9 完成后重跑；若"旧有新无"仍显著非 0，逐条判读是"有意删除"还是"搬迁丢失"。注意这是**辅助信号**：消息可能被拆成模板拼接，整条字面量比对必然有假阳性，不能当硬门禁用。

## t10 前置（任务未开卡，实施前已完成的独立件：迁移脚本与测试）

> 为什么提前做：迁移只依赖"已冻结的 v4 样本 + 已定的 v5 规格"，与 t6–t9 无耦合；而它是本需求
> **数据完整性风险最高**的一件（34 条真实需求 / 97 个任务）。提前实测，t10 开卡时只需补
> 依赖 t9 的收尾（删遗留兼容分支等）。

| 复核项 | 命令 | 结果 |
|--------|------|------|
| 真实样本 dry-run | `node --import tsx/esm scripts/migrate-ledger.ts --file <样本> --dry-run` | 34 需求 / 97 任务不变；差异路径 **22 条全部在白名单内，白名单外 0 条** |
| 实际数据变更 | 同上输出 | 唯一非空变更 = **C7 sheet source 判别联合（20 项，全属 REQ-2e9473 的验收单）**；C3/C4/C5/C6/C8/C9/C10 在真实数据上均为空操作 |
| `--apply` | 同上 | 写入成功；计数不变（34/97/2）；自动备份 `.bak-req47939a-<epoch>`；无 `.tmp` 残留 |
| `--verify` | 同上 | 已是 v5 且结构自洽（statusHistory 齐、无 projectId/parentId、source 全为对象、scope 齐） |
| 幂等 | 再跑 `--apply` | "无需迁移"、无操作 |
| 损坏输入保护 | 对截断 JSON 跑 `--apply` | 拒绝且**原文件字节级未被改动**（md5 比对） |
| 可回滚 | 从备份还原 | 还原后 schemaVersion=4、34 条需求完好 |
| 单元测试 | `npx vitest run tests/migration.test.ts` | **9 passed**（样本白名单 + C3/C4/C6/C7/C8/C9/C10 逐项语义的合成用例） |

**方法论要点**：真实样本里 7 项变更是空操作——**"空操作通过" ≠ "逻辑正确"**，所以合成用例不可省（否则一次全过会伪装成实现正确）。

---
<!-- t6 复核产物锚点（发起窗口落盘时间戳）：本行为 t6 开卡后由发起窗口追加，作为"汇报文件 mtime ≥ 开工时间"的可核验锚点。 -->
<!-- t7 复核产物锚点：发起窗口在 t7 开卡后追加本行。 -->
<!-- t8 复核产物锚点：发起窗口在 t8 开卡后追加本行。 -->
<!-- t9 复核产物锚点：发起窗口在 t9 复核期间追加本行（满足 done 凭证门"汇报文件 mtime ≥ 开工时间"）。 -->
<!-- t10 复核产物锚点：发起窗口在 t10 复核期间追加本行。 -->
<!-- t11 复核产物锚点：发起窗口在 t11 复核期间追加本行。 -->
<!-- t12 复核产物锚点：发起窗口在 t12 复核期间追加本行。 -->
