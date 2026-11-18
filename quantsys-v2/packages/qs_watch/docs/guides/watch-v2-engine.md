---
title: 盯盘引擎 V2 —— 持仓驱动主流程（定时任务版）
type: guide
status: active
owner: 用户（PI Investment）
updated: 2026-10-24
req: REQ-261022235419-2299
---

# 盯盘引擎 V2 —— 持仓驱动主流程（定时任务版）

## 是什么

V2 是**持仓驱动**的盯盘主流程，全部代码在
`qs_watch/application/services/watch_engine/v2/`。

**2026-10-24 用户裁定：V2 上线、V1 判定循环下线。**
V2 不再起常驻循环，改由 5 个 Job 按**规则档位**驱动；三个扫描档各拆成多条调度行，避免开盘前和午休空跑：

| 任务 | 时间（周一~五） | 作用 |
|---|---|---|
| `watch_open_am` | 09:25 | 全部 active 规则取价 → 重算档位 |
| `watch_open_pm` | 13:00 | 午休后重算档位 |
| `watch_scan_30s`（4 条调度） | 09:30-11:30 / 13:00-15:00 每 30 秒 | 本档（30s）规则：判定 + 归档 + 重算档位 |
| `watch_scan_10m`（3 条调度） | 09:30-11:30 / 13:00-15:00 每 10 分钟 | 本档（600s）规则 |
| `watch_scan_30m`（3 条调度） | 09:30-11:30 / 13:00-15:00 每 30 分钟 | 本档（1800s）规则 |

扫描档均不含午休与 15:00 收盘时点，与连续竞价门的结束时刻口径一致。

档位含义（`watch_rules.watch_tier`）：靠近触发线 → 30 秒；距离越远 → 10 分钟 / 30 分钟。
开盘任务与各档位任务都会按最新价重算并回写。**agent 规则一旦进入触发循环，本轮完成前固定
30 秒档**，第 10 次成功投递或条件回落后再恢复距离定档，避免慢档每天到不了第 10 次。
无法价格化的条件使用求值结果 `distance_ratio` 调档，数据 degraded 时保持原档。
规则自己的 `active_window` 在取价前生效，畸形窗口 fail-open；持仓查询正向覆盖规则状态，
空仓止损仍进持仓模块 fail-open。

## 判定流程（每档每票）

```
门（交易日 + 连续竞价 09:30-11:30 / 13:00-15:00，否则零取价零写库）
  → 加载本档 active 规则
  → 逐票取价
  → 失效判定（全票，止损豁免）→ invalid：落 rule_state + 投递 agent 裁决
  → 按持仓分类：holding → position_engine（增仓/止盈/止损/减仓）
                none    → unpositioned_engine（买入/观察）
  → 命中：先在 watch_triggers 落台账（边沿触发闩锁；engine='v2'）
  → 观察类只归档不投递；direct 在新边沿直发飞书；agent 走 10 次循环路由
       第 1 次 → agent；第 2~9 次 → 跳过；第 10 次 → 飞书盯盘群并归零
  → 按真实投递结果回写 notified；agent/direct 成功后才推进或归零 cycle_count
  → agent 首发处置后逐条调用 POST /api/watch/triggers/{id}/agent-complete
       保存 agent_response → V2 notify_feishu(after_agent) 发群
       → 更新 disposition + process_state=processed
```

`watch_trigger` 载荷携带 `rule_id` 与 `trigger_ids`。agent-ts 通过
`watch_manage(action=complete)` 回传 `decision_action/reason/disposition/account/qty`，
不得直接调用飞书工具发本次盯盘卡片。完成接口复用 `watch_triggers.agent_response`
保存结构化裁决和 `notification_delivered`；已成功发群的重复回调只补状态，不重复发卡。
发送失败时裁决保留、处置不完成，agent 可修正后重试。

归档失败时本轮不投递、不推进计数；发送失败时保留下一轮重试同一路由和同一 trigger。
闩锁按交易日 + 规则 + 条件管理，条件回落独立重新武装，无报价不会误解除闩锁。

## 模块

| 模块 | 职责 |
|---|---|
| `scheduled.py` | 定时任务编排：时段门、本档过滤、归档、档位回写 |
| `archive.py` | 投递前落触发台账、投递后回写 `notified`、条件级边沿闩锁 |
| `engine.py` | 股票与市场判定链：失效 → 分类 → 归档路由；观察类不投递 |
| `position_engine.py` | 持仓四操作；止损空仓/状态不可知 fail-open |
| `unpositioned_engine.py` | 非持仓（买入范围 / 观察） |
| `market_watch_service.py` | 市场快照与市场/板块规则评估，后续复用 V2 路由 |
| `condition_evaluator.py` | 两类规则共用的普通条件与 staged_break 求值 |
| `evaluation_context.py` | 价格历史、盘中时间比例、按需均量/日 K/资金流 |
| `data_providers.py` | V2 均量、日 K 和资金流 provider |
| `rule_evaluator.py` | 20 日均量缓存、超时、失败 TTL 与熔断保护 |
| `staged_break_manager.py` | 触及 → 观察 → 确认 / 过期的状态机与运行态恢复 |
| `invalidation.py` | 失效判定：偏离 > agent 失效线 → invalid；**止损豁免** |
| `router.py` | 10 次循环：首发 agent / 2~9 不处理 / 第 10 次直通群并归零 |
| `tier.py` | 档位纯函数（30/600/1800，按距触发线远近） |
| `notify_agent.py` / `agent_prompts.py` | agent 通道 + 提示词（含失效裁决专用模板） |
| `notify_feishu.py` / `feishu_templates.py` | 飞书盯盘群通道 + 模板 |

两通道文件互不 import（有单测断言）；两文案文件同理。

## 开关与部署

```bash
WATCH_V2_ENABLED=true     # 注册 5 个定时任务（关闭 = 一个都不注册）
```

- **V1 股票判定入口已删除**：不再提供 `WATCH_V1_ENABLED` 或 V1 `run_forever` 回滚路径；
  股票触发只由 V2 产生。
- **旁路服务保留**：sidecar 仍跑摘要门、元触发复核、持仓生命周期联动（新仓自动补止损）、
  持仓板块映射、走势回填、池级对账、消息监控、收盘体检日报和政策盯盘线程。
  **没有这些，新仓不会自动补止损。** V1 股票 tick 与 15 阶段管线已删除。
- 迁移：`20261023_watch_rules_tier.py --apply`（加 `watch_tier` 列 + 播种 5 条
  `quant.scheduler_tasks`）。未跑迁移时 `register_watch_v2_jobs()` 会预检拒绝注册。
- 宿主：FastAPI 5001 lifespan；V2 任务注册进 `JobRegistry`，由 APScheduler 按
  `scheduler_tasks` 的 cron 行触发（含 6 段秒级 cron）。

## 每日重置

`v2_daily_cycle_reset`（16:35 周一~五）：**仅活跃规则** `cycle_count=0`、`process_state='pending'`，
次日从循环首发（agent 先处理）重新开始。

- **活跃口径**：`rule_state='active'` 且启用且未过期——仓储 `_active_conditions()` 单点定义，
  `list_by_state('active')` 与 `reset_active_cycles()` 共用。
- **非活跃不重置**：`invalid` / `archived` / 停用 / 过期规则保持原样。

## 数据字段

| 字段 | 语义 |
|---|---|
| `watch_tier` | 30 / 600 / 1800 秒（档位） |
| `trigger_channel` | `agent`（默认）/ `direct` |
| `process_state` | `pending` / `processed` |
| `cycle_count` | 0..9 循环计数（per-rule 独立） |
| `engine` | `v1`/`v2` 触发来源标记（`watch_rules` 与 `watch_triggers` 都有） |

`watch_triggers.engine` 由 `record(..., engine='v2')` 显式写入（2026-10-24 补齐 ORM 映射）；
`compare_v1_v2.py` 只认这一列，缺它时 V2 触发会被算成 V1。

## 对账

```bash
python scripts/compare_v1_v2.py --date 2026-10-24
```

按 `watch_triggers.engine` 分组出 V1/V2 触发数与一致率；切换后 V2 应有数据、V1 应为 0。

## 已知边界

- `staged_break` 在持仓/非持仓规则中共用：触及和观察不通知、不计循环；确认才进入正常
  路由；过期只写 `suppressed=True` 归档。`WATCH_RUNTIME_PERSIST_ENABLED=false` 时观察态
  只在内存保存，重启会丢失；开启后由运行态仓储恢复，跨天自动清空。
- 市场级规则（`scope=market/sector`，如 `held_sector_pct`）由 30 秒档调用市场服务
  自身的扫描节流，复用 V2 归档与路由；不再进入个股取价或 V1 管线。市场/板块观察信号
  不按股票纯观察静默。
- 股票 `trend_observe` 只归档、不唤醒 agent；抑噪期规则每日只留 suppressed 样本、不通知。
- V1 sidecar 的摘要门仍开（`WATCH_DIGEST_ENABLED=true`），可能对未处置项再唤醒一次 agent；
  如确认重复打扰，置 false 即可（不影响其它 sidecar 能力）。
