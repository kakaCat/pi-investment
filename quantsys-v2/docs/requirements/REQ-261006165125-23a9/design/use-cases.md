# 设计 · 用例与消息口径（每日任务空结果不发飞书）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7

## 1. 角色与关注点（serves: FR-2, FR-5）

| 角色 | 关注 | 本设计给的答案 |
|---|---|---|
| 项目所有者（人） | 飞书只在该响的时候响 | 无事 → 0 条；有事 → 1 条；失败 → 1 条 🚨 |
| 运维修数据的人 | 静默之后还查得到 | 台账 + `GET /api/jobs/inprocess/today` + `inprocess_job_notify_skipped` 日志 |
| 窗口 AI Agent | 别把失败一起静默了 | 失败路径不经过判据（interfaces.md §6） |

## 2. 场景矩阵（每条都给出"飞书条数"作为可验收的观测量）（serves: FR-1, FR-2, FR-3, FR-4, FR-6, FR-7）

| # | 场景 | 触发/示例 | 飞书 | 台账 | FR |
|---|---|---|---|---|---|
| UC-1 | **定时任务无事** | `event_calendar_check` 返回 `{'status':'no_event',...}` | **0 条** | `success`，result 原样 | FR-2 |
| UC-2 | 定时任务有产出 | `kline_update` 返回 `{'updated': 5200}` | 1 条「✅ 每日任务完成」（**无**开始消息） | `success` | FR-2, FR-3 |
| UC-3 | 长任务 | `evening_pipeline` 跑 62 分钟且有产出 | 2 条：「⏳ 仍在运行」（第 60 秒）+「✅ 完成」 | `success` | FR-3 |
| UC-4 | 长任务且最终无事 | 同上但 `no_output=True` | 1 条：「⏳ 仍在运行」（**不**发完成） | `success` | FR-2, FR-3 |
| UC-5 | handler 抛异常 | 任意任务 | 1 条「🚨 每日任务失败」，**无**开始消息 | `failed` | FR-4 |
| UC-6 | 内层失败（未抛异常） | result 含 `{'kline_sync': {'status':'error'}}` | 1 条 🚨 | `failed` | FR-4 |
| UC-7 | 无事但 result 自称失败 | `{'status':'no_event','success':False}` | 1 条 🚨（**失败优先**） | `failed` | FR-4 |
| UC-8 | 人工触发（无事） | `POST /api/jobs/inprocess/event_calendar_check/run` | **1 条**「✅ 每日任务完成（人工触发）」 | `success` | FR-6 |
| UC-9 | 开关打开（回滚态） | `DAILY_JOBS_NOTIFY_NOOP=true` + UC-1 | **2 条**：立即开始 + 完成 | `success` | FR-7 |
| UC-10 | 开关打开 + 零产出 | 同上 + `no_output=True` | 2 条，完成消息用 **⚠️（无有效产出）** 语气 | `success` | FR-7 |
| UC-11 | 交易日门跳过（既有） | 休市日的 `pool_daily_refresh` | **0 条**（本次不改） | `skipped` | FR-5 |
| UC-12 | **事件真的来了** | `event_calendar_check` 返回 `{'status':'notified','high':1,...}` | 2 条：事件卡片（`health.py` 自己发的「🚨 未来2日高优事件预警」）+ 任务完成消息 | `success` | FR-1, FR-2 |

**UC-12 是本次的语义锚点**：判据只在"什么都没发生"时沉默；一旦有事件被提醒，任务完成消息照发
（因为 `status='notified'` 不在白名单，`is_no_op=False`）。这保证静默**不会**吃掉"事件已推送"的确认。

## 3. 三个易混场景的显式区分（serves: FR-1, FR-4）

1. **"无事" vs "没跑"**：无事有台账行（`success`）；没跑没有行（`not_run`）。
   飞书两者都安静，靠台账区分——这是 FR-5 的意义。
2. **"无事" vs "失败"**：`result` 里同时出现 `no_event` 与 `success=False` 时**判失败**（UC-7），
   因为漏一条失败告警的代价远高于多一条噪音。
3. **"无事" vs "跳过"**：跳过是"今天这份活不该干"（交易日门），无事是"干了，但没有产出"。
   两者都静默，但台账 status 不同（`skipped` / `success`），本设计不改跳过的分支位置。

## 4. 用户可感知的净变化（serves: FR-2, FR-3）

以 2026-10-06 的 9 个在册任务为例（对照需求文档 E9：`event_calendar_check` 连续 4 天 `no_event`、每天 2 条）：

| 任务类型 | 现状条数 | 新条数 |
|---|---|---|
| 无事且秒级完成 | 2 | **0** |
| 有产出且秒级完成 | 2 | **1**（少一条"我开始了"） |
| 有产出且超过阈值 | 2 | **2**（开始消息换成"仍在运行"） |
| 失败 | 1～2 | **1**（🚨，必达） |

方向上：**消息条数只减不增**，且减少的全部是"没有信息量"的那一类。
