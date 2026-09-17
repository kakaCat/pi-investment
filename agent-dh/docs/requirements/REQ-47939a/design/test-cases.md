# REQ-47939a 技术设计 · 测试用例（不变量 → 可执行断言）

> 上游：`../requirement.md` §5 不变量、§7 验收标准；`domain-model.md` §4 映射表。
> 原则：**测行为不测实现**。重构允许实现测试重写，但不变量测试必须逐条存在且可证伪。

## 1. 测试分层与落位

| 层 | 目录 | 依赖 | 能测什么 |
|----|------|------|---------|
| L1 领域单测 | `tests/domain/*.test.ts` | 纯函数，零 I/O、零 store | 状态机表、规约判定、验收单生成/返工、rollup 决策、产物分类、文档同步 |
| L2 用例测试 | `tests/application/*.test.ts` | 内存 `ReqboardRepository` + 假 `DocRepository`/`Clock`/`IdFactory` | 用例编排、前置/后置条件、幂等、跨聚合一致性 |
| L3 契约测试 | `tests/output-contract.test.ts`（已有，保留并扩展） | 真工具对象 | 工具 schema 合法 + 返回键 ⊆ 声明键（静态穷尽 + 动态成功路径） |
| L4 路由测试 | `tests/http/*.test.ts` | 真 store（临时目录）+ 真 handler | HTTP 状态码/code 映射、与用例同源（不再各写一遍校验） |
| L5 客户端测试 | `tests/client-*.test.ts`（已有） | jsdom | 渲染结构不变（P1 拆分后必须全绿） |
| L6 机械门禁 | `tests/layer-boundary.test.ts`、`tests/size-budget.test.ts` | 源码文本 | 依赖方向、适配层无状态判断、文件行数上限 |
| L7 迁移测试 | `tests/migration.test.ts` | 构造的 v4 台账样本 | 迁移幂等、白名单差异、损坏输入拒绝 |

## 2. 不变量 → 用例矩阵（每条给出断言）

### INV-1 状态机与人工闸门（L1 `tests/domain/requirement-status.test.ts` / `task-status.test.ts`）
- `canReqTransition('draft','brainstorming','agent')` → ok；`('brainstorming','decomposing','agent')` → `{ok:false, code:'human_gate'}`
- 遍历 `REQ_TRANSITIONS` 表：对每个 (from,to) 断言 `canReqTransition` 的结果与表一致（**表驱动**，新增状态不会漏测）
- 遍历 `HUMAN_ONLY_REQ_TRANSITIONS`（cancel/归档相关）：actor=`agent` 一律 `human_gate`；actor=`human` 通过
- 任务侧同一组断言 + 越权窗口：`openerWindow !== actorWindow` 且非本窗口任务 → `not_bound_to_window`

### INV-2 单点实现 + 适配层无状态判断（L6 `tests/layer-boundary.test.ts`）
- 扫描 `src/domain/**`：不得出现 `from 'node:` / `../application` / `../adapters` / `@deepseek-ai/` / `Date.now()` / `Math.random()`
- 扫描 `src/application/**`：不得出现 `node:` / `../adapters` / `cordis`
- 扫描 `src/tools/**` 与 `src/http/**`：不得出现正则 `/status\s*===\s*'|===\s*'(draft|brainstorming|planning|decomposing|implementing|accepting|archived|done|canceled)'/`（状态判断只在 domain）
- 断言扫描器**至少命中 N 个文件**（防扫描器自身失效而静默通过——2026-09-17 契约扫描器踩过这个坑）

### INV-3 幂等（L2 `tests/application/decompose.test.ts`）
- 已拆分需求再 `Decompose` → `{ok:false, code:'already_decomposed'}`，且台账任务数不变
- 同一产物二次提交 → `registered:false` 且 `artifacts` 条数不变
- `Decompose` 连续调用两次 → 第二次拒绝且**不产生幽灵任务**（断言 tasks.length 与首次相同）

### INV-4 done 凭证门（L1 `tests/domain/done-evidence.test.ts` + L2 `move-task.test.ts`）
- 无 `lastReport` → `{ok:false, code:'done_evidence_missing'}`，reason 含"未汇报"
- 有汇报但 `filesChanged` 与 `completed` 皆空 → 拒绝
- 开工以来本窗口无真实工具动作（`windowToolActivitySince === 0`）→ 拒绝
- 距上次 done 转移 < `doneThrottleMs` → `{ok:false, code:'bulk_close'}`
- 页面插件任务（`packages/pages/*`）且 `clientBuildFresh === false` → `stale_build`
- 全部满足 → ok；且断言拒绝路径**没有**改台账（读前后 revision 相同）

### INV-5 rollup R1/R2/R3（L1 `tests/domain/rollup.test.ts`）
- 全部任务 done 且状态 `implementing` → 决策含 `{to:'accepting', rule:'R2'}`
- 存在非 done 任务 → 无 R2 决策
- `draft` 需求无 pending 建议卡 → 决策含 `{to:'brainstorming', rule:'R1'}`（pickup reconcile）
- 已 `accepting`/已归档 → 不产生决策（幂等）
- 断言决策**只描述**（纯函数不改入参对象：`Object.freeze` 输入后调用不抛）

### INV-6 验收单与返工（L1 `tests/domain/acceptance-sheet.test.ts`）
- `buildSheet`：每任务一条（criterion=任务 acceptance，evidence=该任务 lastReport 摘要）+ 需求级一条
- `applyVerdicts` 传 `failed` 且无 opinion → 抛 `invalid_input`（"不通过必须写意见"）
- 有 failed → 返回 `reworkTasks` 每项带 `{title, context: 原意见}`，且 sheet 项状态置 `failed`
- 续版：`buildSheet` 只包含 `pending` + `failed`（已 `passed` 项不再出现）→ v2 只验未过项
- 全 passed → `isAllPassed` true；有任一 pending → false

### INV-7 产物（L1 `tests/domain/artifact.test.ts` + L7 落盘）
- `kindForRelPath('docs/requirements/REQ-abc123/plan.md')` → `plan`；`.../prototype.html` → `notes`；`packages/x.ts` → `task_output`
- `requiredArtifactsFor('planning', 'feature')` 与现有 `STAGE_ARTIFACT_REQUIREMENTS` 逐条一致（表驱动断言）
- `archiveDocRulesFor('bug')` 必填文档与合并去向与 `ARCHIVE_DOC_RULES` 一致
- `checkArchiveMaterials`：缺必填文档 → 拒绝并列出缺哪份；目录内存在未列入清单的文件 → 返回 `unlisted_files` 警告（不阻断）
- 证据路径不存在 → 拒绝（`invalid_input`，消息含该路径）

### INV-8 迁移无损（L7 `tests/migration.test.ts`）
- 用现网台账的**脱敏副本**（34/84/2，见 `fixtures/ledger-v4-sample.json`）跑迁移 → 白名单外 diff 为 0
- 白名单内差异数正确：`projectId/parentId` 删除数 = 样本中存在数；`dependsOn` 悬空剔除数 = 样本中悬空数
- 幂等：迁移两次结果相同（`--apply` 第二次无操作）
- 损坏输入（非法 JSON / 缺 requirements）→ 抛错且**不改原文件**（断言文件内容字节级不变）
- 回滚：`--apply` 后从备份还原 → 内容与迁移前字节级一致

## 3. 尺寸与机械门禁（L6 `tests/size-budget.test.ts`，对应 A2/A3）

- `src/host/agent-tools.ts` **不存在**（断言 `existsSync === false`）
- 所有 `src/**/*.ts` 单文件 ≤ 400 行（白名单：`shared/protocol.ts` 与生成物除外——但须在测试中显式列出白名单并注明理由）
- `src/domain/` 下无 `node:` 导入（与 INV-2 同源，互相印证）

## 4. 既有 495 个用例的处置规则（防"重构顺手删测试"）

| 类别 | 判定 | 处置 |
|------|------|------|
| **行为测试** | 断言"外部可观察结果"（HTTP 响应、工具返回、DOM 结构、台账状态） | **必须全绿**；仅允许改 import 路径/构造方式，断言不变 |
| **实现测试** | 断言内部函数名/文件路径/私有结构（如直接 import `host/agent-tools.ts`、断言内部 helper） | 允许重写为等价行为断言；**重写必须在任务卡里列明"原断言 → 新断言"对照**，且总数不得减少 |
| **契约测试** | `output-contract` / `tools-schema` / `plugin-schema.smoke` | 必须全绿且**增强**（新增 9 工具覆盖） |

判定方式：逐文件标注（在 `decomposing` 阶段的变更盘点里出这份标注表），不允许"先删掉跑绿再说"。

## 5. 9 个工具的语义等价对照（验收 A5 + 回归 A7）

| 收敛后工具 | 覆盖原入口 | 等价断言（逐条） |
|-----------|-----------|----------------|
| `reqboard_create` | create | 入参/返回体不变；两问确认流程不变 |
| `reqboard_status` | status | `next_actions` 与 domain 的 `agentNextActions` 一致 |
| `reqboard_move` | move | 拒绝对应错误码与消息不变（human_gate 附 `gate_question`） |
| `reqboard_decompose` | decompose | 幂等拒绝、`invalid_dag`、薄卡拒绝三条件逐一覆盖 |
| `reqboard_task_move` | task_move | 开工返回任务卡全文；done 凭证门；rollup 触发 |
| `reqboard_task_report` | task_report | 追加段落、`lastReport`、files 上浮 |
| `reqboard_submit` | requirement_submit / plan_submit / verify_submit / archive_submit | 按 `kind` 分派到 4 个独立用例；4 组入参/返回体与现状逐一对应；**断言内部不是一个大 if**（L6：分派表驱动，`switch` 分支仅一行调用） |
| `reqboard_ask_confirm` | ask_confirm + confirm_artifact | 弹框路径 + 文字证据路径（`evidence` 核验）+ `fallback=board` 三条路径；返回键全声明 |
| `reqboard_accept_sheet` | accept_sheet | 逐项弹框/记录/返工/续验/全过终确认五条路径 |

**A7 重放**：对 REQ-2e9473 / REQ-6f39b5 / REQ-9f4a44 各构造"关键操作序列"脚本（创建→提交→确认→拆分→任务推进→验收），在新实现上重放，断言每步的状态与拒绝条件与历史台账记录一致。

## 6. 验收命令（A1-A7 对应）

```bash
cd agent-dh/packages/pages/dsh-pmboard
npx vitest run                                    # A1 全量绿（含新增 L1/L2/L6/L7）
wc -l src/**/*.ts | sort -rn | head                # A2 无文件 >400 行
node -e "console.log(require('fs').existsSync('src/host/agent-tools.ts'))"   # A2 输出 false
npx vitest run tests/layer-boundary.test.ts       # A3 依赖方向 + 适配层无状态判断
node scripts/migrate-ledger.mjs --file <真实的> --dry-run   # A4 白名单外 diff = 0
npx vitest run ../../../../tests/plugin-schema.smoke.test.ts # A5 schema 合法（9 工具）
pnpm build:client && node scripts/verify-client-build.mjs    # A6 客户端构建 + 哨兵
node scripts/replay-req.mjs REQ-2e9473 REQ-6f39b5 REQ-9f4a44 # A7 重放一致
```
