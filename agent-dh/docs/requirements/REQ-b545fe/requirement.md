# REQ-b545fe 修复流水线节点 token 统计漏记（状态迁移统一走快照结算）

## 背景与现象

用户报障（2026-09-20，附截图）：需求详情页流程图 7 个节点（立项→需求分析→技术设计→拆分→实施→验收→归档）中，
只有「立项 1.3M」与「实施 87.0M」两个节点显示 token 消耗，其余 5 个节点无任何数值。

节点 token 能力由 REQ-a33899 交付，口径（docs/architecture/reqboard-token-usage.md）：
**节点消耗 = 进入该节点的状态事件快照 → 离开该节点时的快照之差，同会话才相减；任一端缺失则该段「无快照」，绝不用 0 冒充。**

## 复现步骤

1. 访问任一已归档需求的详情页（如 http://localhost:13080/dashboard/reqboard/requirements/REQ-xxxx）
2. 查看页面顶部流程图（立项→需求分析→技术设计→拆分→实施→验收→归档）
3. 观察各节点下方是否显示 token 消耗数值
4. **预期**：经过的全部节点都显示 token（或诚实标注「无快照」）
5. **实际**：只有「立项」「实施」两个节点显示数值，其余节点空白

curl 验证：
```bash
curl http://localhost:13080/dashboard/api/reqboard/requirements/REQ-xxxx/token
# 查看 data.byStage —— 只有 draft 和 implementing 两个 key，其余节点缺失
```

## 根因（代码级核实）

快照结算函数 `accumulateStageDelta`（packages/pages/dsh-pmboard/src/application/internal/token-usage.ts:68）
**只在 MoveRequirement 用例（reqboard_move）一条路径被调用**（use-cases/MoveRequirement.ts:113-114）。

而需求状态迁移共有 5 条代码路径，其余 4 条全部绕过结算，只 `recordStatus` 不带快照：

| 路径 | 位置 | 典型迁移 | 缺什么 |
|---|---|---|---|
| ① reqboard_move | use-cases/MoveRequirement.ts:113-119 | 窗口手动推进 | ✅ 有结算（唯一正常路径） |
| ② ask_confirm 自动推进 | use-cases/AskConfirm.ts:174-178 | brainstorming→planning、planning→decomposing | 无快照、无结算 |
| ③ rollup 派生推进 | internal/rollup.ts:46-66（advance） | draft→brainstorming（接手）、planning→decomposing、implementing→accepting | 无快照、无结算 |
| ④ 验收通过归档 | use-cases/AcceptSheet.ts:95-99 | accepting→archived | 无快照、无结算 |
| ⑤ 验收打回返工 | internal/verdicts.ts:132-136 | accepting→implementing | 无快照、无结算 |

后果：凡是经 ②③④⑤ 离开的中间节点（需求分析/技术设计/拆分/验收）**永远没有离开快照**，
`entrySnapshotFor` 两端判定不成立，`byStage` 永远缺这些 key，UI 节点自然无 token。
截图中恰好只有「立项」（draft→brainstorming 走过 reqboard_move）和「实施」（implementing→accepting
走过 reqboard_move）有数值，与根因完全吻合。

## 目标

1. **收敛迁移单点**：新增唯一的需求状态迁移助手（结算离开节点 + 新事件带快照 + 写状态），
   上述 5 条路径全部改走它，消灭"改了状态但没结算"这一类 bug 的结构性土壤。
2. rollup 路径能取到快照时结算（use-case 内调用处有 deps.session + windowKey）；
   取不到的调用处（启动对账、无 sessionId 的 HTTP 人工操作）诚实降级为「无快照」，不伪造。
3. HTTP 看板任务操作（routers/tasks.ts，body 带 sessionId 时）接入快照提供者，
   使人从看板推进任务触发的 implementing→accepting 派生推进也能结算「实施」节点。
4. 修复后：新需求走完整生命周期时，全部经过的节点都有 token 数值（取不到投影的诚实显示无快照）。

## 边界

**修复范围**：
- ✅ 需求状态迁移的 5 条代码路径（MoveRequirement/AskConfirm/rollup/AcceptSheet/verdicts）全部接入快照结算
- ✅ 新增唯一迁移助手 transitionRequirement 供全部路径共用
- ✅ rollup 路径扩展可选快照提供者（use-case 有会话传快照，启动对账无会话诚实不传）
- ✅ HTTP 路由接入 SessionProbe 使看板人工操作也能结算

**不修范围**：
- ❌ **历史数据不回填、不伪造**：已归档需求缺失的节点段保持「无快照」（会话投影是累计计数器，历史差值不可考；伪造就违背 REQ-a33899 口径）
- ❌ 任务状态迁移路径（本 bug 只涉及需求状态；任务的 MoveTask 已有快照结算，无此问题）
- ❌ token 口径本身（四分桶、同会话才相减、负差截断等规则不动）
- ❌ 状态机转移规则（assertReqTransition / HUMAN_ONLY_REQ_TRANSITIONS 保持原样）
- ❌ RollupSpec 纯函数决策层（planRollup / planPickupAdvance 等不动，只改落地副作用层）

**复现前提**：
- 需求已走过完整生命周期（至少经过 brainstorming→planning→decomposing→implementing）
- 中间迁移至少有一次走 ②③④⑤ 路径（如 ask_confirm 推进、rollup 自动跳转）
- REQ-a33899 token 功能已上线（2026-09-18 后创建的需求）

## 非目标 / 红线

- **历史数据不回填、不伪造**：已归档需求缺失的节点段保持「无快照」
  （会话投影是累计计数器，历史差值不可考；伪造就违背 REQ-a33899 口径）。
- 不改 token 口径本身（四分桶、同会话才相减、负差截断等规则不动）。
- 不改任何状态机的转移合法性规则（assertReqTransition / 人工闸门保持原语义）。
- RollupSpec 纯函数决策层不动——只在落地副作用层（rollup.ts advance）加快照。

## 回归

**防止回归措施**：

1. **单测覆盖全部 5 条迁移路径**：
   - tests/token-transition-helper.test.ts：核心助手单测（有快照/无快照两种场景）
   - tests/token-usage.test.ts：MoveRequirement 路径补充
   - tests/ask-confirm-transition.test.ts：AskConfirm 推进路径
   - tests/rollup-snapshot.test.ts：rollup 有/无快照提供者场景
   - tests/accept-verdicts-snapshot.test.ts：AcceptSheet 归档 + verdicts 打回路径
   - tests/http-router-snapshot.test.ts：HTTP 路由快照接入

2. **既有回归测试**：
   - tests/artifact-gates.test.ts（ask_confirm 场景）
   - tests/routes-rollup.test.ts（rollup 场景）
   - tests/accept-sheet-tool.test.ts（归档场景）
   - tests/verdicts-and-rework.test.ts（打回场景）
   - tests/token-fallback.test.ts（无快照降级场景）

3. **端到端门禁**（t7 验收标准）：
   - 新建测试需求走全流程，curl 核对 byStage 包含全部经过节点
   - 流程图目视验证每个节点显示 token
   - pnpm test && pnpm typecheck 全绿

4. **代码审查 checklist**：
   - 所有需求状态迁移必须且只能通过 transitionRequirement 进行（grep 'req.status =' 不应出现在 use-cases/ 内，rollup.advance 除外且已改造）
   - RollupContext 必须带 snapshot 提供者（use-case 调用方传、启动对账不传）
   - verdicts.applyVerdicts 签名必须有 snap 参数且调用方传值

## 验收标准

1. 单测：构造需求依次经 ②③④⑤ 路径迁移，断言每个离开节点的 byStage 都累加了正确差值
   （假快照源，递增计数）；快照不可得时断言不记值（无快照而非 0）。
2. 回归：既有 token 相关测试（token-fallback / rollup / verdicts / accept-sheet 等）全绿。
3. 端到端：重建 pmboard 客户端 + 重启后，新建一条测试需求走「确认推进→拆分→任务完成→验收归档」
   全流程，流程图每个经过节点显示 token（或诚实无快照），curl /requirements/:id/token 核对
   byStage 键覆盖全部经过节点。
4. 文档：docs/architecture/reqboard-token-usage.md 的落点说明更新为「全部迁移路径统一经迁移助手结算」。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

> 本需求文档尚未定义功能点编号。

<!-- reqboard:marks:end -->
