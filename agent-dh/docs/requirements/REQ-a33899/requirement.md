# REQ-a33899 项目看板：记录并展示每个流程节点（阶段过程）的 Token 消耗

- **需求类型**：feature　**状态**：需求分析（brainstorming）
- **提出**：用户　**分析**：investor / w-b11b0a40（窗口 session-b11b0a40）
- **提出原话**：「项目看板插件需要一个记录每个过程消耗token的记录，你懂」
- **档位说明**：宿主注入 brainstorming/light/feature（DEFAULT_DIFFICULTY=light）。本需求**触发 L3 单向升级信号**
  （① 要改数据模型：台账 schema v5→v6 新增 token 快照字段；② 出现多个未定决策）→ 已按 heavy 方法论手动执行
  （探索上下文 → 澄清提问 → 方案对比 → 分节设计）；**档位只升不降**。

---

## L1 一句话目标 + 可证伪判定标准

**目标**：项目看板（dsh-pmboard）把「每个流程节点 / 每个任务执行」消耗的 token 落成台账并可展示，
让「这个需求的 token 都花到哪里去了、固定提示词占了多少」在一处看得见。

**可证伪判定标准**（跑什么、看到什么算完成）：

1. 推进一个需求跨 2 个以上流程节点后，GET /dashboard/api/reqboard/req/<REQ>/token 返回 byStage 中
   **至少 2 个节点**有非零 uncachedInputTokens + outputTokens，且各节点数值等于该节点区间内执行会话
   tokenUsage 投影累计值的差值（人工用同一投影文件核对一致）。
2. 打开需求详情页 → 出现第 5 个 tab「🪙 Token」，能看到：按节点汇总的四分桶 + 费用估算、
   点开节点下钻到该节点每个任务的消耗、以及「固定提示词影响」一块。
3. 会话顶部需求进度条上，**每个节点**旁显示该节点已消耗 token（与判定 1 的数字一致）。
4. 看板卡面显示该需求累计 token（与判定 1 的合计一致）。
5. 取不到快照时（服务不可得 / 人从看板点按钮推进且无快照），对应条目显示**「无快照」**
   且**不得出现编造数字**（返回 null/缺省，前端显式标注）。

## L2 范围边界（做什么 / 不做什么）

**做（3 条）**：
1. **写时快照**：在节点推进（状态转移）与任务执行（开工/完工）的写路径上，把执行会话的
   tokenUsage 累计快照（含 seq）落进台账；节点/任务消耗 = 两次快照之差（用户裁定的归属口径）。
2. **需求详情页新增「Token」tab**：只针对**当前这一个需求**，展示该需求的 token 去向——
   按节点汇总（四分桶 + 费用估算）→ 下钻到每个任务的消耗 → 「固定提示词影响」一块。
3. **两个轻量展示面**：会话顶部需求进度条上每个节点显示已消耗 token；看板卡面显示需求累计 token。

**不做（明确排除）**：
- **不做需求之间的对比/排行**（用户原话：「不做需求的对比，只是看这个需求token都花到哪里了」）——
  不新增跨需求榜单页；看板不新增独立「Token 看板」页，只新增详情页 tab。
- **不做读时派生为主**（用户已裁定「只做写时快照」）：不以查询时实时解析会话文件为权威口径；
  会话文件缺失/人点按钮推进导致的空档，如实标「无快照」，不反推。
- **不做精确费用账单**：费用是**估算**（按可取得的模型单价折算，取不到则显示—），不承诺与供应商账单逐分对账。

## L3 升级依据（为什么不是轻档）

- 改动**数据模型**：ReqboardLedger schema v5 → v6（StatusEvent / ExecutionRecord / RequirementRecord
  增加 token 快照字段）——L3 明示的升级信号之一。
- 新增跨层数据通路：host 侧读 DSH 会话 tokenUsage 投影 → 写台账 → 3 个展示面消费。
- 结论：按 heavy 档方法论执行（本文档即其产物），后续 planning/decomposing 亦按 heavy 走。

---

## 3 澄清记录（全部经 ask_user_question 逐问确认）

| # | 问题 | 用户裁定 |
|---|------|---------|
| 1 | 记录粒度与字段 | **节点汇总 + 可下钻到每次执行**（四分桶 + 折算费用） |
| 2 | 归属口径与留存 | **只做写时快照（落台账持久）**（不采用读时派生/混合） |
| 3 | 展示位置 | 会话顶部**每个节点**显示 token；**看板卡面**；需求**详情页新增 tab**；实施里细化到**每个任务** |
| 4 | 新 tab 范围 | **项目看板详情里的 tab**，不做需求对比；看「这个需求 token 花到哪里」＋**固定提示词对 token 的影响** |

## 4 数据源实测证据（R-013：来源 + 时点 + 口径）

| 数据 | 来源（实测） | 口径与时点 |
|------|-------------|-----------|
| 会话累计 token（四分桶） | DSH sessionProjections.stateOf(session, tokenUsage) → totals:{uncachedInputTokens, outputTokens, cacheReadTokens, cacheWriteTokens}；投影缓存文件 <dshHome>/storages/session_projcache/sessions/<sessionId>.json 的 record.rows.tokenUsage 同形状 | provider 上报累计；实测样本 session-d751fab4：uncachedInput 123136 / output 87492 / cacheRead 8693632（2026-09-18 读投影缓存） |
| 逐 step usage 明细 | 会话 JSONL 事件 type=usage（实测该会话 73 条，字段含 inputTokens/outputTokens/cache*） | 历史事件流，逐 step |
| 会话统计 | 同投影 sessionStats（turns/steps/llmMs/toolMs/decodeTokens） | 同上 |
| 费用（按日/模型） | <dshHome>/dsh-usage/usage-ledger.json → days[date][provider][model].cost | **按天聚合，非按会话**；逐会话费用需按模型单价折算 |
| 固定提示词注入 | <dshHome>/state/prompt-injection-log.json（reqboard 已落）：{at,windowKey,stage,difficulty,category,routeKey,hitLevel,fragmentIds,charCount,trimmed} | 每回合注入留痕，ring buffer 500 条；**charCount 是字符数（token 代理指标）** |

> 数据源降级纪律：sessionProjections 不可得（服务未装配/测试环境）→ 快照记 null 并标 source=unavailable，
> 禁止用旧值/记忆值冒充（对齐宪法第 5 条与 R-013）。

## 5 接口与数据契约（feature 档）

### 5.1 共享类型（src/shared/protocol.ts）

    /** token 四分桶（与 DSH tokenUsage 投影逐字段对齐，不重命名以免口径漂移）。 */
    export interface TokenBuckets {
      uncachedInputTokens: number; outputTokens: number; cacheReadTokens: number; cacheWriteTokens: number
    }
    export function emptyBuckets(): TokenBuckets
    export function addBuckets(a, b): TokenBuckets
    export function subBuckets(a, b): TokenBuckets   // 负值截断为 0 并标注
    export function totalTokens(b): number           // 四桶之和（展示口径单点）

    /** 写时快照（来源可核验：取不到就缺省，不伪造）。 */
    export interface TokenSnapshot {
      sessionId?: string; seq?: number; at: number; totals: TokenBuckets;
      source: 'projection' | 'unavailable'
    }

### 5.2 台账字段（ReqboardLedger schema v5 → v6）

- StatusEvent.tokenSnapshot?: TokenSnapshot —— 每次节点转移时记录**执行会话当时**的累计值；
  节点消耗 = 进入该节点的转移快照 → 离开该节点的转移快照之差（同 sessionId 才相减）。
- ExecutionRecord.tokenUsage?: { start?: TokenSnapshot; end?: TokenSnapshot; delta?: TokenBuckets; costEstimateCny?: number }
  —— 任务执行的起止快照与差值（「下钻到每次执行」的数据来源）。
- RequirementRecord.tokenUsage?: { byStage: Partial<Record<StageKey, TokenBuckets>>; totals: TokenBuckets; costEstimateCny?: number; updatedAt: number; promptImpact?: PromptImpact }
  —— 读路径 O(1) 的聚合快照；由写路径增量维护。
- PromptImpact = { injections: number; chars: number; estTokens: number; sharePct?: number }
  —— 「固定提示词影响」：注入条数 / 字符数 / **估算 token**（注明估算系数）/ 占需求总量比例。

**必填性**：以上字段**全部可选**（老台账无此字段必须可载入）；缺失 ≠ 0，UI 显示「无快照」。

### 5.3 HTTP 接口（/dashboard/api/reqboard，信封 {success,data}）

- GET /req/:id/token（新增）→ { requirementId, totals, costEstimateCny?, byStage: [{stage, buckets, executions:[{taskId,title,delta,start?,end?}], promptImpact}], promptImpact, degraded }
- GET /session/:sessionId/progress（扩展）→ 每个节点对象增加 tokens?: {total:number, buckets:TokenBuckets}
- GET /state（扩展）→ 需求卡增加 tokenTotals?: number（卡面展示）

### 5.4 写入点（写时快照的唯一入口）

- sessionProjections 端口升级：新增 tokenTotals(windowKey|session): TokenSnapshot | undefined；
  SessionProbeAdapter 做实现（读不到 → source=unavailable，不抛错、不阻断主流程）。
- 节点转移写路径（MoveRequirement / recordStatus）与任务写路径（MoveTask 开工/完工、ReportTask）落快照
  —— **主流程不因取快照失败而回滚**（快照是旁路证据）。

## 6 迁移与兼容

- REQBOARD_SCHEMA_VERSION 4→…→**6**；读路径对新增字段**一律可选解析**（v5 及更早台账直接可载入，
  不自动迁移——沿用 design/migration.md §5 既有策略）。
- 迁移脚本 scripts/migrate-ledger.ts 增 v5→v6 分支：仅 **bump schemaVersion + 留 migrations 留痕**，
  **不伪造历史快照**（历史节点的 token 无从取得，宁缺勿造）。
- 回滚：token 字段是纯附加数据，回滚即删字段/忽略；不影响状态机与既有闸门。

## 7 验收（可执行）

1. pnpm -C packages/pages/dsh-pmboard test 全绿（新增 tests/token-usage.test.ts：
   快照差值、缺席「无快照」、四分桶聚合、promptImpact 估算、乐观降级）。
2. pnpm -C packages/pages/dsh-pmboard typecheck 通过。
3. 端到端：对一个测试需求 reqboard_move 两次（跨 2 节点）后，
   curl -s localhost:13080/dashboard/api/reqboard/req/<REQ>/token 返回 byStage 两节点非零，
   且与投影文件 tokenUsage.totals 差值一致（附命令与输出到 verification.md）。
4. 页面：详情页出现「🪙 Token」tab（grep -c 'data-tab="token"' lib/client.js ≥1）；
   会话顶部进度条节点含 token 文本；卡面含累计 token。
5. 负样本：人为让 sessionProjections 不可得 → 接口 degraded=true、相关条目为「无快照」且**无编造数字**。

## 8 风险与待确认

| 风险 | 说明 / 缓解 |
|------|-----------|
| 人从看板点按钮推进无会话上下文 | 写时快照取不到 → 该段标「无快照」（用户已知悉并选择此口径） |
| 一个会话同时推进多个需求 | 快照按**会话**累计，节点差值含同期他需求消耗 → 在 tab 内**显式标注口径** |
| 费用需模型单价 | 取不到单价 → 费用显示—，token 仍展示；估算口径写进 UI tooltip |
| 固定提示词 token 是字符折算 | charCount → token 为**估算**（系数单点常量 + UI 标注），不冒充 provider 上报 |
| 快照未覆盖 subagent | 子会话 token 是否并入挂起：**本期不并入**（另一未定决策），tab 内注明 |

---

**下一步**：planning —— 用 reqboard_ask_confirm(target=artifact, kind=requirement) 交棒；未获批准不得进入。
