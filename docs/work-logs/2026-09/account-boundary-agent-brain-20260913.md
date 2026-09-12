# 账户边界改造：agent-dh 自有账户 = agent_brain（2026-09-13）

- 执行窗口：**w-c8cae280**（investor / 投资脑）
- 起因：用户澄清「agent_brain 是 agent-dh 的（不只 w-a8a89c6a），agent_virtual 是 agent-ts 的」
- 目标：让"默认账户"不再指向别人的账，并让误用**静默失败变成显式拒绝**

## 一、问题实证（改造前）

工具层把 `agent_virtual`（= agent-ts / fin-agent 的账户）硬编码为默认账户：

| 证据 | 数值 | 来源 |
|---|---|---|
| 硬编码点 | 8 个包、约 30 处（`args.account_name \|\| 'agent_virtual'` + prompt `default`/`example`） | grep packages/*/src |
| agent_virtual 收到的成交 | **23 笔**（2026-07-27~09-10），其中 **5 笔 reason 直接引用 agent-dh 规则号**（R-001/R-002/R-007/R-008/R-009、M5-1 验收测试） | quant.simulation_order |
| agent_brain（自有账）成交 | 仅 **3 笔**（2026-08-26 起） | 同上 |
| 涉事例行任务 | 5 个 agent-dh 系统巡检任务（pre-market-routine / afternoon-open-check-live / post-market-routine-live / m4-circuit-breaker-live / weekly-report-m6）owner=investor，**payload 中完全没写账户**，全靠默认值 | public.tasks payload 正则 |

结论：默认值指错账户 ⇒ agent-dh 的例行任务在用 agent-ts 的账下单，且**静默无声**。

## 二、改造内容

### 1) 代码层（源码 + dist 产物）

- **读工具默认账户**：`agent_virtual` → `agent_brain`
  覆盖 trading/risk/strategy/intelligence 四个包（account_info、position_list、portfolio_analyze、trade_verify、trade_monitor、risk_metrics、risk_controller、regime_position_limit、barra、rotation_proposal/simulate、watch_manage 的归属账户、intelligence 行情适配器的 tradeMonitor/getCurrentPosition）。
- **写工具强制显式传参并拒绝 agent_virtual**（新增 R-019 护栏，插在各自 `validate()` 内）：
  `portfolio_trade`、`algo_execute`、`cancel_pending_order`、`m4_circuit_breaker_check`、`rotation_execute`
  - 缺 `account_name` → INPUT_ERROR：`写操作必须显式传 account_name（agent-dh 自有账户 = agent_brain）`
  - 传 `agent_virtual` → INPUT_ERROR：`agent_virtual 属 agent-ts（fin-agent），agent-dh 禁止对其写入`
- rotation 三件套原本还残留 `|| 'default'`（已冻结的 legacy 账户），一并改为 agent_brain。
- 持仓看板默认账户：`board-mount.ts` / `holdings-routes.ts` / `portfolio-aggregation.ts` 默认由 agent_virtual 改为 agent_brain（看板保留账户切换器，其他账户仍可查看）。

### 2) 任务层（public.tasks payload，12 条）

- 5 个系统巡检任务：追加【账户纪律 R-019】段，明确所有账户类工具必须显式传 `account_name="agent_brain"`。
- 7 个 agent-brain-* 任务：原文「（工具默认 agent_virtual，禁止作用错账户）」→「（工具默认已改为 agent_brain，仍须显式传参，R-019）」。

### 3) 规则层（genome）

- `rules` v19 → **v20**（genome g33），候选 `cand_1789238124323_t8dryn`，commit `7fb6eb6`，R-019 新增、无规则删除、结构复核通过。
- 同批修正 R-018 ③ 的口径错误：原文把"买入决策 20 日平均超额为负"当作自己的业绩先验 —— 实测该 27 条评分 **100% 是策略线账户 v13/v14 的回填**（2026-06-29~07-13，全创业板，基准 sh000300，窗口重叠、同标的同日重复最多 3 次），**agent_brain 覆盖 0 条**。新口径：必须按账户过滤并写明覆盖样本数，覆盖为 0 时如实写"无自有样本"。

## 三、验证

| 项 | 结果 |
|---|---|
| 插件 schema 冒烟 | `tests/plugin-schema.smoke.test.ts` 19/19 通过 |
| R-019 护栏单测（新增） | `tests/account-guard.test.ts` **17/17 通过**（5 写工具 × 缺参/agent_virtual/agent_brain 三态 + 源码无残留默认值 + 4 读工具默认值断言） |
| dist 构建 | `restart-with-build.sh --build-only` → 19/19 包构建并校验通过；trading dist 命中护栏 4 处、strategy 1 处 |
| L1/L2 体检 | 依赖符号链接 OK、dist 产物 OK |
| 持仓看板 client | `build:client` 重出 lib/client.js（45106 B，含 agent_brain） |

## 四、遗留

1. **需要重启 :13080 才真正生效**（插件从 dist 加载 + host 侧 src 重载）。
2. `quant.simulation_order` **无 submitted_by/窗口字段**（只有 genome_version），多窗口共账时无法归属下单者 —— 已作为跨线事项提给后端线（公告板）。
3. 历史污染（agent_virtual 里的 23 笔）不做回滚：那是既成事实，且 agent-ts 侧的账应由 agent-ts 决定处置。
