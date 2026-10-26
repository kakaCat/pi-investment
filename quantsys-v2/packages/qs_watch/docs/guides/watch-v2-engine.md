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
开盘任务与各档位任务都会按最新价重算并回写。

## 判定流程（每档每票）

```
门（交易日 + 连续竞价 09:30-11:30 / 13:00-15:00，否则零取价零写库）
  → 加载本档 active 规则
  → 逐票取价
  → 失效判定（全票，止损豁免）→ invalid：落 rule_state + 投递 agent 裁决
  → 按持仓分类：holding → position_engine（增仓/止盈/止损/减仓）
                none    → unpositioned_engine（买入/观察）
  → 命中：观察类只归档不投递；其余走 10 次循环路由
       第 1 次 → agent；第 2~9 次 → 跳过；第 10 次 → 飞书盯盘群并归零
  → 归档 watch_triggers（边沿触发闩锁；engine='v2'）
```

## 模块

| 模块 | 职责 |
|---|---|
| `scheduled.py` | 定时任务编排：时段门、本档过滤、归档、档位回写、心跳 |
| `engine.py` | 判定链：失效 → 分类判定 → 路由投递；观察类不投递 |
| `position_engine.py` | 持仓四操作；止损空仓/状态不可知 fail-open |
| `unpositioned_engine.py` | 非持仓（买入范围 / 观察） |
| `invalidation.py` | 失效判定：偏离 > agent 失效线 → invalid；**止损豁免** |
| `router.py` | 10 次循环：首发 agent / 2~9 不处理 / 第 10 次直通群并归零 |
| `tier.py` | 档位纯函数（30/600/1800，按距触发线远近） |
| `notify_agent.py` / `agent_prompts.py` | agent 通道 + 提示词（含失效裁决专用模板） |
| `notify_feishu.py` / `feishu_templates.py` | 飞书盯盘群通道 + 模板 |

两通道文件互不 import（有单测断言）；两文案文件同理。

## 开关与部署

```bash
WATCH_V2_ENABLED=true     # 注册 5 个定时任务（关闭 = 一个都不注册）
WATCH_V1_ENABLED=false    # V1 判定循环下线（V1 sidecar 仍随进程启动）
```

- **V1 旁路服务保留**：V1 只停 `run_forever` 判定循环；sidecar 仍跑摘要门、元触发复核、
  持仓生命周期联动（新仓自动补止损）、持仓板块映射、走势回填、池级对账、消息监控、
  收盘体检日报，以及板块共振/政策盯盘线程。**没有这些，新仓不会自动补止损。**
- 迁移：`20261023_watch_rules_tier.py --apply`（加 `watch_tier` 列 + 播种 5 条
  `quant.scheduler_tasks`）。未跑迁移时 `register_watch_v2_jobs()` 会预检拒绝注册。
- 宿主：FastAPI 5001 lifespan；V2 任务注册进 `JobRegistry`，由 APScheduler 按
  `scheduler_tasks` 的 cron 行触发（含 6 段秒级 cron）。
- 回滚：`WATCH_V2_ENABLED=false` + `WATCH_V1_ENABLED=true`，重启即回 V1；
  `watch_tier` 列与任务行可保留（V1 不读）。

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

- `staged_break`（两段式伏击）是有状态条件，V2 判定层标 `degraded` 跳过
  （生产当前 1 条 entry 规则受影响，无止损规则使用该条件）。
- 市场级规则（`scope=market`，如 `held_sector_pct`）仍由 V1 市场扫描承担；
  V2 不做市场级扫描（生产当前 1 条观察规则）。
- 观察类只归档、不唤醒 agent（与 V1「观察也推送/聚合」不同）。
- V1 sidecar 的摘要门仍开（`WATCH_DIGEST_ENABLED=true`），可能对未处置项再唤醒一次 agent；
  如确认重复打扰，置 false 即可（不影响其它 sidecar 能力）。
