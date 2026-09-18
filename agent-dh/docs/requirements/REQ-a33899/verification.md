# REQ-a33899 验收材料

- **需求**：项目看板：记录并展示每个流程节点（阶段过程）的 Token 消耗（feature）
- **交付结论**：写时快照落台账（schema v5→v6，字段全可选）+ 三处展示（需求详情页「🪙 Token」tab / 会话顶部流程条每节点 / 看板卡面累计）+ 提示词成本（固定系统提示词 + reqboard 注入提示词，读时装配）。
- **窗口**：w-b11b0a40（session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

## 1 可复核证据（命令 + 输出摘要）

### 1.1 单测 / 类型 / 客户端构建

    cd agent-dh/packages/pages/dsh-pmboard
    pnpm typecheck   → 通过（tsc --noEmit 零错误）
    npx vitest run   → Test Files 1 failed | 68 passed (69)；Tests 1 failed | 987 passed (988)
                      唯一失败 = tests/board-info-fixes.test.ts「验收态未交材料操作条」
                      **本改动前基线即为红**（改动前基线：1 failed | 940 passed），非本次引入；
    pnpm build:client → tsdown OK；wrap-client OK；verify-client-build: OK bundle=223297 bytes

新增/相关测试（全绿）：tests/token-usage.test.ts(11)、tests/session-probe-token.test.ts(6)、
tests/ledger-v6-token.test.ts(8)、tests/token-endpoint.test.ts(6)、tests/prompt-cost.test.ts(8)、
tests/token-tab.test.ts(5)、tests/token-card.test.ts(3)。

### 1.2 台账迁移（对**线上台账副本**跑，不动线上文件）

    cp <DSH_HOME>/dsh-reqboard.json /tmp/req-a33899-ledger.json   # 线上: .dsh-data/dsh-reqboard.json，v5 / 37 需求 / 130 任务
    node --import tsx/esm scripts/migrate-ledger.ts --file /tmp/req-a33899-ledger.json --dry-run
      before: schemaVersion=5 … requirements=37 tasks=130
      after : schemaVersion=6 … requirements=37 tasks=130
      差异路径 2 条；白名单内 2 条，**白名单外 0 条** → 可执行 --apply
    … --apply → 已迁移并原子替换（自动备份 .bak-req47939a-…）
    … --verify → ✅ 已是 v6 且结构自洽

结论：v4→v5 语义原样保留，v5→v6 只 bump 版本 + 逐段留痕；**历史不伪造 token 快照**（宁缺勿造）。

### 1.3 端到端（真实台账副本 + 真实注入留痕，走 HTTP 全链路）

    脚本：node --import tsx/esm <e2e>.mts（JsonLedgerRepository 读 /tmp 副本 → createReqboardHandler → GET /requirements/REQ-a33899/token）
    status 200
    totals {"uncachedInputTokens":0,...} degraded true   ← 该需求早于功能上线，本就没有快照（如实 degraded，不补 0）
    byStage 7 个节点（buckets 均为 null）
    systemPrompt assembled perTurnChars 254 sections 1     ← 该块以 stub 装配验证接线（真实 assembler 由宿主 systemPrompt 服务提供）
    injections 180 chars 207442
      byStage brainstorming 47634 / planning 47166 / decomposing 2074 / implementing 110568（**真实留痕数据**）
      sample {"stage":"brainstorming","routeKey":"brainstorming/light/feature","chars":1401,...}

说明：过程消耗的非零链路由 tests/ledger-v6-token.test.ts（写时快照差值）与 tests/token-endpoint.test.ts
（读路径/接口）覆盖；线上台账尚无快照是因为功能未发版（见 §3）。

### 1.4 客户端产物核验（线上实际加载的那份文件）

    grep -c 'data-tab="token"' lib/client.js   → 1     # 详情页第 5 个 tab 在产物里
    grep -c 'dsh-pm-tok-table' lib/client.js   → 5     # Token tab 结构
    grep -c 'dsh-pm-flow-token' lib/client.js  → 2     # 会话顶部每节点 token
    grep -c 'dsh-pm-token-badge' lib/client.js → 3     # 卡面/列表累计徽章

### 1.5 文档

- 新增 L2 页 `agent-dh/docs/architecture/reqboard-token-usage.md`（两条口径 / 缺失语义 / 接口 / 自检命令 / 相关页面）；
- 挂进 `agent-dh/docs/README.md` 卷 7（页面插件 GUI）与自动索引 `INDEX.md`（已跑 `python3 agent-dh/scripts/docs_index.py` 刷新）。

## 2 覆盖矩阵（需求 → 证据）

| 需求要点 | 证据 |
|---------|------|
| 写时快照落台账（v6，字段可选） | tests/ledger-v6-token.test.ts；迁移 §1.2 |
| 节点/任务消耗 = 两次快照之差（同会话） | tests/ledger-v6-token.test.ts（差值/跨会话不做减法/不可得不补 0） |
| 详情页「🪙 Token」tab（四折叠块 + 看具体提示词内容） | tests/token-tab.test.ts；§1.4 grep |
| 会话顶部每节点 token（与名称同行，样式不变） | tests + §1.4 `dsh-pm-flow-token` |
| 看板卡面累计 token | tests/token-card.test.ts；§1.4 `dsh-pm-token-badge` |
| 固定系统提示词成本（按段字符→估算 token） | tests/prompt-cost.test.ts；§1.3 |
| 注入提示词成本（按窗口归属 + 按阶段聚合） | tests/prompt-cost.test.ts；§1.3 真实 180 条 |
| 不做跨需求对比；不做读时派生；费用为估算 | 接口只给单需求；写时快照为准；费用见 §3 缺口 |

## 3 已知缺口与未闭环（如实列出，不粉饰）

1. **未发版**：`:13080` 仍加载旧代码（host 半需重启、client 半需重建后刷新）。**这是本需求唯一的最后一公里**；
   发版命令：`agent-dh/scripts/restart-with-build.sh`（relink → build → kickstart）。
   注意：重启会中断当前 DSH 进程（本会话宿主），lifecycle 会自动注入续跑消息。
2. **费用估算恒为「—」**：`costEstimateCny` 字段与 UI 已就位，但**模型单价表未接入**，因此始终显示「—」；
   token 主指标不受影响。接入单价表属后续独立改动。
3. **回合数不可得**：固定系统提示词只给「每回合」成本，不给累计（接口不猜回合数）；接入会话统计后可补。
4. **subagent 子会话 token 未并入**（需求阶段已挂起为后续决策）。
5. **基线红与工具问题（均非本次引入）**：tests/board-info-fixes.test.ts 1 例；
   `scripts/wiki_probe.py` 报 2 条现行页死链（均指向 `INDEX.md` 的 work-logs/requirements 链接）与 1 个孤儿页（INDEX.md 自身）、
   且 `docs_index.py --check` 在重生后仍报不一致（工具自身问题）。

## 4 回滚

- 代码：`git revert` 相关提交即可；schema v6 的新字段是**纯附加数据**，v5 读路径忽略它们，无需数据回滚；
- 台账：若已对线上执行过 `--apply`，用迁移自动产生的 `.bak-req47939a-*` 覆盖回去再重启。
