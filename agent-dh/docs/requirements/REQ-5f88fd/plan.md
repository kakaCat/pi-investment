---
title: REQ-5f88fd 盯盘引擎闭环断链修复：唤醒-记账-归因 · 实施计划
requirement: REQ-5f88fd
category: feature
status: pending_approval
created: 2026-09-15
---

# REQ-5f88fd 盯盘引擎闭环断链修复：唤醒-记账-归因

## 一、背景

2026-09-15 对盯盘引擎做线上体检，结论：**感知完备、行动未接通**。
引擎能触发、能升级、能过五道处置门，但"把触发变成 agent 的行动并记账"这一公里是断的。

> 数据源：生产库 `quant_investment`（schema `quant`，psycopg2 直查，2026-09-15 00:54–01:30）；
> v2 API `http://127.0.0.1:5001`；v2 日志 `logs/launchd-stdout.log`。

## 二、已核实事实

### 2.1 决定性发现：v2 → agent 唤醒通道已断（系统级回归）

| 时点 | 事件 | 证据 |
|---|---|---|
| 09-14 16:30 | v2 `daily_review` 投递成功 | 日志 `Agent notified successfully` |
| 09-14 19:27 | profile 配置中 lifecycle **已被注释** | `cordis.patch.yml.bak-20260914-192711` |
| 09-14 23:00 | v2 `pool_changed` → **HTTP 405** | 日志 `Agent API error HTTP 405` |
| 09-15 01:18 | 实例重启（PID 61323） | `ps` lstart |
| 09-15 01:2x | 探测 `POST :13080/wake` → **405** | 与 `/__definitely_nonexistent__` 行为完全一致 |

- `/wake` 路由**全仓唯一注册者** = `agent-dh/packages/lifecycle/src/wake-webhook.ts`。
- 配置 `agent-dh/.dsh-data/profiles/agent-dh/cordis.patch.yml` 第 259-260 行把该插件注释禁用，
  其 `profileDir` 仍指向已废弃的 `~/.dsh/profiles/investment`（现为空目录）——推断为
  09-14 `.dsh-home → .dsh-data` profile 迁移后的临时措施，但未意识到 `/wake` 亦由 lifecycle 提供。
- 影响面：盯盘摘要唤醒、`daily_review` / `pre_market_summary` / `signals_ready` / `pool_changed`、
  lifecycle 自修复（`self_restart` / `self_finalize` / `self_status` / `self_info`）**全部失效**，
  且 v2 只写日志不告警 → **静默**。

### 2.2 闭环零次

- `watch_triggers.agent_response`：**530/530 全为 null**。
- `watch_interventions`：仅 9 条，全部 `outcome=escalated`，`tokens=None`、`cost_yuan=0`、
  `decision_audit_id=None` → **规则级 ROI 无法计算**。
- 根因：`application/services/watch_engine/engine.py` 调 `ledger.record()` 时**未传**这三个字段。

### 2.3 摘要门被影子模式锁死，积压 106 条

- `GET /api/watch/triggers/digest` 实测 `gate=true, count=106`
  （`meta_review 65 / escalated 26 / pending 15`），最老积压 **84 小时**（2026-09-11 13:00 起）。
- `.env:52-54`：`WATCH_DIGEST_ENABLED=true` 但 `WATCH_DIGEST_DRY_RUN=true` → 只记日志、从不唤醒。
- `watch_digest_state` 全空：`wake_count=0`、`last_wake_at=null`、`last_digest_at=null`。
- 按 `linked_account` 分段结果为 **4 段**（user_main_simulation 39 / agent_brain 26 /
  未归属 21 / agent_virtual 20）→ 首次转正将一次投 4 份、消耗 4/8 预算。

### 2.4 系统自诊断无人消费

65 条 `meta_review` 的 reason 全为「频次超限：单日触发 7~21 次 ≥ 5 → 规则需复核」，且
`notified` **全为 False**。设计上 `meta_review_service` 的产物「进未处置清单 → 会被摘要唤醒带走」，
**没有独立通道**，与买点信号抢同一摘要。

### 2.5 预算门：正确工作，但额度与触发量不匹配

> ⚠️ 本项为**自我修正**：初判"预算门形同虚设（26>8）"系误读——26 是状态机上线以来累计值，
> 9-14 当日实际 escalated **恰好 8 条 = `daily_budget=8`**，预算门**按设计正常工作**。

真实问题：**8 次/天 vs 126 触发/天**，09-14 **13:00 即耗尽**，之后 118 条触发全部失能，
且被拦者落 `auto_observed`（reason「预算门…→ 进日终汇总」），而**日终汇总从未运行**。

`disposition.decide()` 真实门序：宪法豁免（`exit_stop`，可突破预算）→ 预算门 → 引擎升级 → L2 行动层 → 五道门。
仅 `exit_stop` 能突破预算；`pending` 不计入预算（`engine` 仅在 `disposition=='escalated'` 时记账），口径不一致。

### 2.6 噪声与僵尸规则

- 09-14 单日 **126 次触发 / 仅 12 条规则**；top 规则 72 次。
- `rule 21`（`pnl_pct>10%`）平均间隔 **1207 秒**重复触发 15 次。
- 45 条启用规则中 **8 条从未触发**（rule 139/134/127/107/104/103/102/101）；
  rule 107 宁德时代「下破 320」vs 现价 336+，典型阈值漂移。

### 2.7 可观测性缺口

- 530 条触发 `detail->>'trigger_level'` **全为 null**（触发时未落库，仅通知时现算）。
- `watch_rules.burst_count_window` / `noise_triggers` 恒为 0（死字段）。
- `/api/watch/triggers/unresolved` 默认按「当天」过滤（今日返回 0），而实际积压 106，
  与 `digest` 端点语义不一致，易误判为"队列已清空"。

## 三、目标与非目标

**目标**：把感知结果接通到 agent 行动并记账，使「哪条规则真的赚钱」可回答。

**非目标**：感知层（条件评估 / 升级检查 / 去重 / 状态机）已于 2026-09-14 重构完成并验证，
本次**不改**；也不新增策略类型（历史方案中 `VolatilityStrategy` 等无证据支撑，已废弃）。

## 四、任务分解

| key | 任务 | phase | side | 依赖 |
|---|---|---|---|---|
| t1 | 恢复 `/wake` 唤醒通道 | implement | backend | — |
| t2 | 摘要门 fail-safe 与端到端验证 | test | backend | t1 |
| t3 | 存量 106 条积压消化 | implement | backend | t2 |
| t4 | 摘要门转正 + 首次唤醒观测 | implement | backend | t3 |
| t5 | 触发终态自动登记（agent_response） | implement | backend | t4 |
| t6 | 介入记账补齐三元组 | implement | backend | t5 |
| t7 | meta_review 独立通道 | implement | backend | t4 |
| t8 | 预算额度与触发量匹配 | implement | backend | t4 |
| t9 | 可观测性补齐 | implement | backend | — |

**跨仓提示**：t1 落在 **agent-dh**（profile 配置），t2–t9 落在 **quantsys-v2**（Python 后端）。

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| t1/t4 需重启 :13080，**会中断当前 agent 会话** | 先落 `pending-resume`，重启后按续跑清单验证；配置改动前备份 `cordis.patch.yml` |
| t4 转正后唤醒失败 | `maybe_wake` 已有 fail-safe：投递不成功返回「唤醒通道失败（不写状态，下次重试）」且不消耗预算；异常时回退 `dry_run=true` |
| 首次唤醒一次投 4 段 | t3 先定义存量消化策略，避免 4 份大载荷同时涌入 |
| 改盯盘读链路影响交易 | 本次**只读**触发/记账链路，不触碰下单与风控 |

## 六、验收标准

1. `POST http://127.0.0.1:13080/wake` 合法 payload 返回 `200 {"success":true}`；v2 日志出现 `Agent notified successfully: watch_digest`。
2. 交易时段内至少 1 次真实唤醒：`watch_digest_state.wake_count >= 1` 且 `last_wake_at` 非空。
3. 一次真实处置后 `watch_triggers.agent_response` 非空。
4. 新 `watch_interventions` 记录 `tokens/cost_yuan/decision_audit_id` 均有真实值。
5. `/api/watch/triggers/unresolved` 与实际积压一致（不再出现"当天 0 条"的误导）。
6. 回归：`pytest tests/ -k "watch"` 全绿（基线 271 passed, 1 skipped）。

## 七、备注

本次探索中另有两处**自我修正**已落库（见 memory `analysis` 命名空间）：
①预算门诊断（见 2.5）；②`notify_agent` 返回值——初判"返回字符串致失败被误判成功"，
核实为其内部 `== 'ok'` 返回 **bool**，`if ok:` 正确，**不是 bug**。
