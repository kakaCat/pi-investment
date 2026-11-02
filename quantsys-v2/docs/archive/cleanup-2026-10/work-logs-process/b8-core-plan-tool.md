# B8：core 建仓计划加 DSH 工具入口（计划 + 新鲜度 + 与持仓差额）（2026-09-13，w-a9ec14d7）

## 背景：三个消费端都在硬编码文件路径直读 JSON

`quantsys-v2/config/core_plan.json` 由定时任务 `core_plan_generate`（工作日 09:05）生成，
**三个** Agent OS 例行任务靠硬编码路径直读它：

| 任务 | cron | 用途 |
|---|---|---|
| agent-brain-core-plan | 09:10 工作日 | 主例行：校验 plan、核对暴露/持仓/子额度、**核对与当前持仓的差额** |
| agent-brain-candidate-hunt | 08:45 工作日 | 把 holdings 当候选池（strategy_registry 的 core-overlay-v1，source=core_plan） |
| agent-brain-live-order-test | 一次性 | 从 holdings 里挑标的做最小真实单测试 |

直读文件有三个问题：

1. **路径知识散落在各任务提示词里**，改一处要改 N 处；
2. **读不出"陈不陈"**——周五的计划周一照样读得出来，内容看着完全正常。
   主例行任务自己写着"generated_at 必须是今天且不早于 09:00，否则判生成失败并停止"，
   而这恰恰是最容易被跳过的一步（没有任何机制强制）；
3. 主例行第 2 步要求"核对**与当前持仓的差额**"，而服务端**从未产出过这个差额**——
   只能靠 agent 每次手工比对。

## 改动

### v2：`plan_snapshot()` 只读视图 + `GET /api/core-plan`

`application/services/core_plan_service.py` 新增：

- `_plan_freshness()`：机械判定 + **理由文本**（`is_stale` / `stale_reason` / `generated_today` /
  `generated_after_deadline` / `age_hours`）。只判定并给理由，**不替调用方决定要不要停**。
- `_plan_delta()`：目标组合 vs 当前持仓的机械差额。只读（走 `SimulationPositionRepository`，
  不刷行情、不下单、不改库）。每行含 `target_shares / held_shares / shares_available / delta_shares /
  action / est_amount`，并带 6 条 `caveats`。
- `plan_snapshot()`：汇总三块，并处理三种"不可用"情形（文件缺失 / 无法解析 / **账户不匹配**），
  每种都给 `unavailable_reason`。

**账户不匹配守卫**：计划只服务单一账户。显式请求不同账户时返回 `account_mismatch=true`
且**不给差额**并说明原因——跨账户算差额是错数据，不静默。

### 顺带修掉两处使差额"算不出来"的产物缺陷

1. **core 持仓原先不存 `lots`**：`generate()` 只在打印时算一遍手数就丢了，产物里只有
   `weight_pct_of_core`。消费方拿不到"目标股数"，它要求的"差额"**根本无从算起**。
   现已把 `lots` 与 `amount` 写进产物（口径与打印循环完全一致）。
2. **产物原先没有 `data_date`**（行情时点），只有 `generated_at`（生成时刻）。
   周末/节假日重跑或行情未同步时，生成时刻是新的、行情却可能是旧的，只看 generated_at 发现不了。
   现已写入 `data_date`。这与"signals.strategy_id 应自描述策略名"是同一条教训：
   **产物要自描述，别让消费方去反推。**

### 接口刻意不转 key

`/api/core-plan` **不使用 `api_response()`**：那个 helper 会递归把 key 转成驼峰，把计划自身的
`generated_at`/`weight_pct_of_core` 变成 `generatedAt`/`weightPctOfCore`，
于是**同一份计划出现两套 key 词汇表**（文件里蛇形、接口里驼峰），读文件的三个任务与走接口的
调用方看到的结构不一致。这正是"同一状态两种定义"的事故面（本仓已因此出过真实故障：
self_finalize 与 boot-recovery 对同一退出状态定义相反）。故原样返回，只做 `sanitize_for_json`。

### agent-dh：`core_plan` 工具（只读）

- `quantsys-v2-client`：新增 `getCorePlan(account?)` + `CorePlanSnapshot` 等类型（纯增量 92 行）。
- `packages/investment/src/tools/CorePlanTool/`：工具三件套，注册进 investment 插件（第 20 个工具）。
  render 把**新鲜度放在第一行**（过期时首行即 "⚠️ core 计划已过期（不要按它建仓）"）。
- `available=false`（文件缺失/无法解析/账户不匹配）**按成功返回**：它带 `unavailable_reason`，
  是有信息量的正常结果；包装成工具错误只会让模型看到"调用失败"而丢掉原因。

## 验证

1. **纯增量证明**：B8 前后逐字段比对 —— 新增 31 个字段（`data_date` + 15×`lots` + 15×`amount`），
   **丢失 0 个**；共有字段仅 3 处变化（`generated_at` + 2 处已知的 PG 并行聚合末位抖动）。
2. **stdout** 与最初 psql 基线仍逐字节一致（除实时接口 `/api/market/sectors` 那一行）。
3. **接口实测**：重启 v2 → `GET /api/core-plan` 返回真实差额
   （17 只 BUY、约 62,696 元 = core 50,906 + 成长板 11,790，整手取整后）。
   账户不匹配守卫实测：请求 `agent_virtual` → `account_mismatch=true`、`delta=null` + 原因。
4. **构建产物验证**（关键）：`investment` 与 `quantsys-v2-client` 的 main 都指向 **dist**，
   源码绿灯证明不了线上生效。故构建后：
   - 校验 dist 含新符号（`getCorePlan`×2、`core_plan`×5、"这不是委托清单"×1）；
   - 新增 `tests/plugin-dist.smoke.test.ts`：**按包自己声明的 main 构造插件**（与 DSH 加载路径一致），
     覆盖 15 个 dist-main 包。构建前备份 dist（构建失败会先清空 dist → 插件消失）。
   - 结果：dist 冒烟 15 passed + 源码冒烟 19 passed = 34 passed。
5. profile 链接体检：`relink-profile.py --check` → symlink-ok=25（无硬链接副本漂移）。

## 遗留（诚实）

- **DSH 侧尚未做进程内实测**：dist 已重建，但运行中的 DSH 仍持有旧模块，需要一次重启才能让
  `core_plan` 工具真正出现在工具列表里。重启走 `self_restart`，而生命周期检查点会把
  **`agent-dh/` 整个目录**（`add -A -- agent-dh/`）提交到 wip 分支——当前
  `agent-dh/docs/requirements/REQ-24e15d/` 是**另一个窗口的未提交产物**，会被一并带进我的
  wip 分支、并随 `self_finalize(merge)` 合入 main。故**先征求用户意见**再重启，不擅自连带他人工作。
- 本工具**不能**证明 dist 与源码同步（陈旧 dist 照样构造成功）——那一层只能靠"构建后校验"，
  已在测试文件头注明能力边界。

## 提交

- feat(v2): core 建仓计划只读 API + DSH core_plan 工具（B8）
