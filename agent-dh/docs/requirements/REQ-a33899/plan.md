# REQ-a33899 技术设计 / 实施计划（planning · heavy）· v2

- **需求**：REQ-a33899《项目看板：记录并展示每个流程节点（阶段过程）的 Token 消耗》
- **需求文档**：docs/requirements/REQ-a33899/requirement.md（已人工确认）
- **档位**：heavy（v5→v6 数据模型变更触发 L3 升级；档位只升不降）
- **状态**：待批准（批准后方可 reqboard_decompose 落库任务）
- **v2 修订**（按用户意见）：「缺少 html 展示 / 一个 tab 怎么设计 / 会话顶节点怎么展示 token」→
  补 design/ui.md + design/token-ui.html（渲染图 token-ui.png）；会话顶部 token 改**与节点名同行水平放置**；
  Token tab 增**固定系统提示词**与**注入提示词**两块成本展示。
- **数据源实测**（2026-09-18）：会话 tokenUsage 投影 totals 四桶；会话 JSONL type=usage 逐 step；
  dsh-usage/usage-ledger.json 按天 cost；state/prompt-injection-log.json 注入留痕；systemPrompt.assemble() 段清单。

## 1 目标

把「每个流程节点 / 每个任务执行」的 token 消耗用**写时快照**落进 reqboard 台账（schema v5→v6，字段全可选），
并在三处展示：需求详情页新增「🪙 Token」tab（节点汇总 + 任务下钻 + **固定系统提示词** + **注入提示词**）、
会话顶部进度条每节点 token（与名称同行）、看板卡面累计 token。**不做**跨需求对比、**不做**读时派生为主、费用与字符折算为估算。

## 1.5 UI 设计（原型 + 结构）

- **可交互原型**：[design/token-ui.html](./design/token-ui.html)；**渲染图**：[design/token-ui.png](./design/token-ui.png)
- **设计文档**：[design/ui.md](./design/ui.md)（布局、DOM、类名、交互与空态/降级态、数字格式单点）
- **详情页 Token tab（分块折叠，沿用既有 details.dsh-pm-fold）**：常显汇总卡（总/未缓存输入/输出/缓存读/费用估算）+ 四个折叠块——
  📊 按流程节点（表格，行可下钻任务，默认展开）／🧱 固定系统提示词／💉 注入提示词／ℹ️ 口径说明。
- **固定系统提示词块**：合计行（本次装配字符 · 每回合估算 token · 回合数 · 累计）＋ **每段一个二级折叠，可展开查看该段的【具体提示词内容】**（只读 pre-wrap，max-height 内滚动）；
  同理注入提示词块每次注入一个二级折叠，展示该次注入内容摘要与命中片段。
- **会话顶部（现有样式不变）**：圆点在上、名称在下（.dsh-pm-flow-node 列布局不动），名称行内**水平**加 token 小字（立项 3.2k / 实施 428.5k / 无快照—）；悬停 title 给四分桶与费用；复用既有 15s 轮询。
- **卡面**：meta 行一枚 🪙 徽章；无数据不渲染。

## 2 技术方案（数据流）

    A. 过程消耗（写时快照）
    执行会话（sessionProjections.stateOf(session,'tokenUsage')）
      → 端口 SessionProbe.tokenTotals(windowKey|session): TokenSnapshot
      → 写路径快照：节点转移（StatusEvent.tokenSnapshot）/ 任务执行（ExecutionRecord.tokenUsage.start|end|delta）
      → 聚合维护 RequirementRecord.tokenUsage.byStage|totals
      → 读路径 QueryRequirementToken + QueryStageDetail（每节点 token）
    B. 提示词成本（读时装配，不进台账）
    systemPrompt.assemble(scope).sections/contexts/tools → 逐段字符 → 估算 token（固定系统提示词，每回合都付）
    state/prompt-injection-log.json（routeKey/fragmentIds/charCount）→ 阶段聚合 + 明细（reqboard 注入提示词）
      → 并入同一 token 接口
    C. 出口
    HTTP：GET /requirements/:id/token（新）、/session/:id/progress（扩展 tokens）、/state（扩展 tokenTotals）
      → client：详情页 Token tab、会话顶部进度条、看板卡面

**写时快照纪律**：
- 快照是**旁路证据**——取不到（服务未装配/非会话上下文）→ 记 source=unavailable 或缺省，**主流程不因此失败**。
- 节点消耗 = 「进入该节点的转移快照」→「离开该节点的转移快照」差值，**同 sessionId 才相减**；跨会话不做减法。
- 历史（v5 及更早）不伪造快照，迁移只 bump 版本号。
- 提示词成本是**读时装配**（不算进台账）：固定系统提示词随代码/基因组变化，落台账会过期失真；
  接口返回时标注 source=assembled|unavailable 与「估算」口径。

## 3 接口与数据契约（精确签名）

### 3.1 src/shared/protocol.ts（新增，t1）

    export interface TokenBuckets { uncachedInputTokens; outputTokens; cacheReadTokens; cacheWriteTokens: number }
    export interface TokenSnapshot { sessionId?: string; seq?: number; at: number; totals: TokenBuckets;
                                    source: 'projection' | 'unavailable' }
    export interface RequirementTokenUsage { byStage: Partial<Record<StageKey, TokenBuckets>>; totals: TokenBuckets;
                                          costEstimateCny?: number; updatedAt: number }
    export interface ExecutionTokenUsage { start?: TokenSnapshot; end?: TokenSnapshot; delta?: TokenBuckets; costEstimateCny?: number }
    // 提示词成本（读时装配）
    export interface PromptPartCost { name: string; chars: number; estTokens: number }
    export interface SystemPromptCost { perTurnChars: number; perTurnEstTokens: number; turns: number;
                                        cumulativeEstTokens: number; sections: PromptPartCost[];
                                        contexts: PromptPartCost[]; toolsChars: number; source: 'assembled'|'unavailable' }
    export interface InjectionItem { at: number; stage: string; routeKey: string; fragmentIds: string[]; chars: number; estTokens: number }
    export interface InjectionCost { count: number; chars: number; estTokens: number; sharePct?: number;
                                     byStage: PromptPartCost[]; items: InjectionItem[] }
    export function emptyBuckets/addBuckets/subBuckets/totalTokens/estimateTokensFromChars/fmtTokens/fmtCny(...)
    export const TOKENS_PER_CHAR = <单点常量>;

### 3.2 台账字段（schema v5 → v6，t3）

- StatusEvent.tokenSnapshot?: TokenSnapshot
- ExecutionRecord.tokenUsage?: ExecutionTokenUsage
- RequirementRecord.tokenUsage?: RequirementTokenUsage
- 全部可选；缺失 ≠ 0（UI 显示「无快照」）。
- REQBOARD_SCHEMA_VERSION = 6；migrate-ledger.ts 增 v5→v6 分支（只 bump + migrations 留痕）。

### 3.3 端口（t2 / t5）

    // application/ports.ts
    interface SessionProbe { ...; tokenTotals(windowKey: string): TokenSnapshot | undefined }
    // adapters/SessionProbeAdapter.ts：sessionProjections.stateOf(session,'tokenUsage') → totals/seq；
    //   服务不可得 / 无会话 → { at, totals: emptyBuckets(), source:'unavailable' }
    // adapters/SystemPromptCostAdapter.ts（t5）：systemPrompt.assemble({scope}) → sections/contexts/tools 字符统计；
    //   服务不可得 → source:'unavailable'（不猜）
    // application/internal/injection-log.ts（t5）：按窗口/需求筛选 + 按阶段聚合 charCount → PromptPartCost

### 3.4 HTTP（t4/t5）

- GET /dashboard/api/reqboard/requirements/:id/token（新增）
  200 {success:true,data:{requirementId,totals,costEstimateCny?,byStage:[{stage,buckets,
      executions:[{taskId,title,delta,start?,end?]}], systemPrompt:SystemPromptCost, injections:InjectionCost, degraded}}
  404 not_found（需求不存在）；degraded=true 表示存在 unavailable 快照/提示词装配不可用（不阻断）。
- GET /session/:sessionId/progress（扩展）：节点对象增 tokens?: {total:number, buckets:TokenBuckets}
- GET /state（扩展）：需求卡增 tokenTotals?: number；缺失不输出该键。

## 4 迁移与兼容

- 读路径对 v6 新字段一律可选解析；v5 及更早台账直接可载入（不自动迁移，沿用既有策略）。
- 迁移脚本对历史记录**不写 token 字段**（宁缺勿造）；migrations 追加 {from:5,to:6,at,by}。
- 提示词成本为读时装配，无迁移问题；systemPrompt 服务不可得时该块显式「不可用」。
- 回滚：忽略/删除纯附加字段即可，不影响状态机、闸门与既有测试。

## 5 任务表（key / 标题 / 阶段 / 端侧 / 依赖 / 可证伪验收）

| key | 标题 | phase | side | 依赖 | 可证伪验收 |
|-----|------|-------|------|------|-----------|
| t1 | 立 Token 契约与纯函数 | implement | fullstack | - | tests/token-usage.test.ts：四桶加减/截断、totalTokens=四桶之和、估算单调非负、fmtTokens/fmtCny 边界；pnpm test+typecheck 全绿 |
| t2 | 会话 Token 读取端口与降级 | implement | backend | t1 | 假 projections→source=projection 四桶一致；服务 undefined→source=unavailable 全 0 不抛 |
| t3 | 台账 v6 + 写路径快照与迁移 | implement | backend | t1,t2 | 跨 2 节点后 StatusEvent 含 tokenSnapshot；任务 start/end/delta；v5 可载入；迁移后 schemaVersion=6 且 migrations 有记录 |
| t4 | 读路径装配与 HTTP（需求/节点/任务） | implement | backend | t3 | curl token 接口返回 byStage+executions；404 正确；unavailable→degraded=true 且无编造数字；progress/state 扩展字段可见 |
| t5 | 提示词成本读路径（系统提示词 + 注入） | implement | backend | t4 | 单测/端到端：systemPrompt 可用→sections 逐段 chars 与 assemble 一致、perTurn=tools+contexts+sections；不可用→source=unavailable 不猜；injections 按阶段聚合 charCount=留痕之和 |
| t6 | 详情页「🪙 Token」tab（汇总卡 + 四个折叠块） | ui | frontend | t4,t5 | 实现与 design/ui.md §1 一致；grep -c 'data-tab="token"' lib/client.js >= 1；一级折叠四块齐全；固定系统提示词每段可展开看到具体提示词内容（pre-wrap，超长内滚动）；无快照显示「无快照」、服务不可用显示「不可用」，均不显示 0 |
| t7 | 会话顶部每节点 Token（同行）+ 卡面累计 | ui | frontend | t4 | 不改既有节点样式（圆点在上/名称在下），仅在名称行内水平加 token（新增 .dsh-pm-flow-meta/.dsh-pm-flow-token，复用既有 .dsh-pm-flow-node/.dsh-pm-flow-label）；卡面含 🪙 徽章；无数据不渲染徽章 |
| t8 | 端到端自证与文档更新 | test | doc | t3,t4,t5,t6,t7 | verification.md 附 curl 输出 + tokenUsage.totals 核对 + 提示词段对照；test/typecheck/build:client 三条命令通过输出；文档登记 token 契约与「无快照/估算」口径 |

**排序依据**（feature 档）：契约（t1）→ 端口（t2）→ 台账写入与迁移（t3）→ 读路径（t4）→ 提示词成本（t5）→ 展示（t6/t7）→ 自证（t8）。
**t6 依赖 t4+t5**（两块提示词都要有数据）；**t7 只依赖 t4**（节点 token 来自 progress 扩展）。

## 6 验收（可执行命令）

    cd agent-dh/packages/pages/dsh-pmboard
    pnpm test          # vitest run 全绿（含 tests/token-usage.test.ts）
    pnpm typecheck     # tsc --noEmit 通过
    pnpm build:client  # tsdown + wrap + verify（client 产物含 token tab 与节点 token）
    curl -s localhost:13080/dashboard/api/reqboard/requirements/<REQ>/token | head -c 1200
    curl -s localhost:13080/dashboard/api/reqboard/session/<sid>/progress | grep -o 'tokens' | head

    # 核对：与 <dshHome>/storages/session_projcache/sessions/<sessionId>.json 的 rows.tokenUsage.totals 差值一致；
    #       系统提示词段字符与 systemPrompt.assemble() 输出的 section 文本长度一致

## 7 风险与缓解

| 风险 | 缓解 |
|------|------|
| 人从看板点按钮推进无会话上下文 | 该段标「无快照」（用户裁定口径，UI 显式标注） |
| 同会话多需求 → 差值含同期他需求消耗 | tab 内口径说明；不做跨需求对比即不放大该偏差 |
| 系统提示词随基因组/工作区变化 | 读时装配（不落台账），接口标 source=assembled + 时点 |
| 费用单价不可得 | costEstimateCny 缺省 → UI 显示—；token 主指标不受影响 |
| 字符→token 为估算 | TOKENS_PER_CHAR 单点常量 + UI 标「估算」，不冒充 provider 上报 |
| subagent 子会话未并入 | 本期不并入，tab 内注明；列为后续独立决策 |
| client 逐行字符串变换禁忌 | 只改 TS 源并走既有 tsdown + wrap-client + verify-client-build，不做行级变换 |

## 8 下一步

批准本计划（reqboard_ask_confirm target=plan / 看板「批准计划」）→ reqboard_decompose 落库任务 DAG → implementing。
未获批准不得拆分实施（代码级 HARD GATE）。
