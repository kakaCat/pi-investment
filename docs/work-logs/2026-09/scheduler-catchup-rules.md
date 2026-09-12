# 定时任务按业务规则补跑（2026-09-13）

> 执行：w-c8cae280（investor）｜用户要求：「我希望定时任务都可以按照业务规则补跑」

## 一、审计：此前**没有实现**（只有检测与手动入口）

| 能力 | 之前状态 | 证据 |
|---|---|---|
| 漏跑检测 | ✅ 有 | `scan_v2`/`scan_agent_os` 按 cron 推算期望时刻比对 runs |
| 告警 | ✅ 有 | 飞书直发 + `quant.scheduler_watchdog_log` 去重 |
| 手动补跑入口 | ✅ 有 | v2 `POST /api/scheduler/tasks/{id}/trigger`、OS `/api/v1/scheduler/tasks/{id}/trigger` |
| 自动补跑 | ❌ **默认关** | `WATCHDOG_AUTO_RERUN=false`，且只有"任务布尔位"一个条件 |
| 最早补跑时刻 | ❌ **死字段** | `compensation_check_after` 只被写进 `params['_compensation_check_after']`，**全仓无读取方** |
| 最大补跑次数 | ❌ **死字段** | `compensation_max_attempts` 同上 |
| 补跑窗口 | ❌ 无 | 任何时间都可能补 |
| 重复防护 | ❌ 无 | 槽位被后续运行覆盖后仍会补 |
| 交易时段感知 | ❌ 无 | 凌晨补盘前例程无业务意义 |
| 补跑留痕 | ❌ 无 | `action` 恒为 `alerted` |
| OS 侧规则 | ❌ 空 | 27 个 OS 任务 `metadata.watchdog` 全 NULL → 全部 alert_only |

（APScheduler 自身的 `misfire_grace_time` 是唯一的"自动补"，仅限进程内 ≤1h。）

## 二、规则模型（判定顺序，任一不过即不补并给出原因）

| # | 规则 | 数据来源 | 默认 |
|---|---|---|---|
| 1 | 一次性任务不补 | `task_type='once'` | — |
| 2 | 授权位 | v2 `compensation_enabled` / OS `metadata.watchdog='auto_rerun'` | 不授权 |
| 3 | **已被后续成功运行覆盖** | 槽位之后该任务是否有 `status='success'` 的运行 | 覆盖则不补 |
| 4 | 次数上限 | v2 `compensation_max_attempts` / OS `metadata.catchup.max_attempts` + `quant.scheduler_catchup_log` 累计 | 1 |
| 5 | 补跑窗口 | v2 默认 12h / OS `metadata.catchup.window_hours` | 12h |
| 6 | 最早补跑时刻 | v2 `compensation_check_after` / OS `metadata.catchup.check_after` | 08:00 |
| 7 | 交易时段 | OS `metadata.catchup.market_hours`（周一至周五 09:30-11:30/13:00-15:00） | 否 |

授权分级（按业务含义，而非"全开"）：
- **A 交易时段敏感**（window 3h / check_after 09:30 / market_hours）：盘前例程、盘中异动扫描、午后开盘检查、晨间账户分析、账户实时检查
- **B 盘后·数据类**（window 12h / 08:00）：熔断回路、市场感知、风格更新、卖出信号生成、权益快照、盘后例程、业绩归因、账户复盘/审计、v2 健康检查
- **C 周度·自主能力**（window 48h / 08:00）：进化蒸馏/裁决/变体、元学习、学习飞轮周报、账户周度蒸馏/进化/ROI
- **D 不授权**（只告警）：一次性核验任务、已禁用任务、**有交易副作用的任务**（v2 `compensation_enabled=false`：`每日信号执行`、`v13/v14-simulation-trading` 等 12 个）

## 三、实现

- 规则引擎：`scripts/scheduler_watchdog.py` 新增纯函数 `catchup_decision()` / `is_trading_now()`（可单测）；
  扫描阶段为每个 missed 槽位附加 `catchup` 规则块（含 `superseded` 覆盖判定）；
  主循环对**所有** missed（不只新告警的）每轮重评 → "未到最早补跑时刻"的任务会在后续轮次自然被再判；
- 留痕表：`quant.scheduler_catchup_log(issue_key, system, task, attempt, ok, reason, created_at)`；
- 总开关：`WATCHDOG_AUTO_RERUN=true`（launchd plist，2026-09-13 开启）；
- 计数持久化：次数上限靠留痕表累计，不会因多轮扫描而无限补跑。

## 四、验证

- 单测 **10 例**：`scripts/tests/test_scheduler_watchdog_catchup.py`（7 条规则 + 时段边界 + 文案完整性）；
- 真实数据判定：对当轮 2 条真实漏跑（238/253 的周六槽位）跑规则 → 均判
  `不补跑：槽位之后已有成功运行，补跑会重复`（我此前手工补跑的结果被正确识别为覆盖）；
- **执行路径 E2E**（合成槽位 + v2 253 无副作用任务）：
  1. 首次判定 `eligible` → `trigger_rerun` 返回 True → 253 出现新运行 `#3675 success 01:28:58`；
  2. 留痕写入 `attempt=1 ok=True reason=eligible`；
  3. 第二次判定 → `max_attempts`（不会循环补跑）；
  4. 把 `superseded` 置真 → `superseded`（重复防护有效）；
  5. 合成留痕已清理，不留测试噪声。
- 规则实测有效：E2E 首次跑用的是默认 `check_after=08:00`，当时 01:3x → 判定
  `before_check_after`（**凌晨不补跑**，符合业务规则）。

## 五、遗留

1. `is_trading_now` 只做"工作日 + 时段"粗判，**未接法定节假日日历**；节假日的补跑由窗口/最早时刻兜底，需要精确时应接交易日历；
2. 是否给 12 个"有交易副作用"的任务中的某些（如 `每日信号执行`）授权补跑，属业务决策——当前一律不授权；
3. v2 侧 `window_hours` 目前只有全局默认（12h），周度 v2 任务若需要 48h 窗口，可写入 `params.catchup`（代码已支持，未启用以免影响任务参数）。
