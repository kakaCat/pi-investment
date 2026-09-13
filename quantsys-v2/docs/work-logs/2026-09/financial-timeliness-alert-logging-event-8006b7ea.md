# 错误事件处置：发送时效性告警失败 Logger._log() got an unexpected keyword argument 'symbol'

- **事件 ID**：`8006b7ea-3e00-4c28-a85c-e4a13b4b6e49`（source=v2，severity=error，logger=`infrastructure.jobs.financial_timeliness_check_job`）
- **处置窗口**：w-32314d00（投资脑 investor）
- **处置时间**：2026-09-13
- **首现/最近**：09-12 09:00 / 09-13 09:00（频次 2）

## 1. 现象

`quant.scheduler_tasks` task 318（`每日财报时效性检查`，cron `0 9 * * *`）每日 09:00 执行，
`last_status=success`，但日志里每次都留下一行 error：

```
logs/launchd-stdout.log:211937: 发送时效性告警失败: Logger._log() got an unexpected keyword argument 'symbol'
```

**任务"成功"、告警"失败"** —— 这个组合正是本次要拆的东西。

## 2. 根因（代码定位，已复现）

`infrastructure/jobs/financial_timeliness_check_job.py`：

- 第 15 行：`logger = logging.getLogger(__name__)` —— **标准库** logger；
- 第 166 行起（修复前）：`logger.warning("financial_timeliness_alert", symbol=..., expected_date=..., message=...)`
  —— **structlog 风格**调用。

标准库 `Logger._log()` 只接受 `exc_info/stack_info/stacklevel/extra`，因此该调用**必然**
抛 `TypeError: Logger._log() got an unexpected keyword argument 'symbol'`；
而异常被同一函数的 `except Exception as e: logger.error(f"发送时效性告警失败: {e}")` 吞掉 →
**告警正文（含超期天数、建议行动）从未落日志**，只留下症状级 error 行。

复现（修复前，本机实测）：

```console
$ ./venv/bin/python -c "from infrastructure.jobs.financial_timeliness_check_job import _send_timeliness_alert; _send_timeliness_alert({...})"
ERROR infrastructure.jobs.financial_timeliness_check_job: 发送时效性告警失败: Logger._log() got an unexpected keyword argument 'symbol'
```

### 为什么连修三天没修好（打地鼠）

| 日期 | error_events 里的症状 | 处理 |
|---|---|---|
| 09-10 | `发送时效性告警失败: column "created_at" of relation "system_logs" ...`（2 条） | 已 resolved |
| 09-11 | `发送时效性告警失败: 'symbol'`（`bd03ca47`） | 已 resolved（把 `check_result['symbol']` 改成 `.get('symbol','全市场')`） |
| 09-12 / 09-13 | `发送时效性告警失败: Logger._log() got an unexpected keyword argument 'symbol'`（本事件） | **本次** |

09-11 那次改的是**取值**，把失败点从"取值"挪到了"调用本身"——掩盖了真正的缺陷
（**logger 类型不匹配**：stdlib logger 不吃任意 kwargs）。教训：
"把异常取值改成兜底值"只挪动了报错位置，没验证**调用本身是否合法**；
修 bug 必须证伪"下一行不会再炸"。

## 3. 落地动作

### 3.1 修调用本身（`financial_timeliness_check_job.py`）

```python
logger.warning(
    "financial_timeliness_alert symbol=%s expected_date=%s\n%s",
    check_result.get('symbol', '全市场'),
    check_result['expected_report_date'],
    message,
)
```

- 用标准库支持的 `%s` 惰性格式化，**告警正文一定能落日志**（与 formatter 无关）；
- 保留 `symbol` 缺失兜底（全市场）与 09-11 的修复意图；
- 异常分支改 `logger.error("发送时效性告警失败: %s", e, exc_info=True)` ——
  告警链路异常必须带栈，否则只能看到"失败"看不到"为什么"（本次两天没定位住的原因之一）。

### 3.2 同类缺陷全仓排查（AST 扫描）

用 AST 扫描 `quantsys-v2` 全部 `*.py`：找出"绑定到 `logging.getLogger(...)` 的变量"上
使用非 `exc_info/stack_info/stacklevel/extra` 关键字参数的日志调用：

```
infrastructure/jobs/financial_timeliness_check_job.py:166: logger.warning(...) 非法 kwargs=['symbol','expected_date','message']   ← 真阳性（本次修复）
infrastructure/logging/config.py:123/283/293/305: 非法 kwargs=[...]                                                ← 假阳性
--- 命中 5 处 ---
```

`config.py` 的 4 处经人工核实为**假阳性**：那里的 `logger` 是 `structlog.get_logger()`
（第 122/280 行），与同文件第 140 行 `logging.getLogger` 同名不同绑定——文件级启发式无法区分作用域。
**结论：全仓仅此 1 处真阳性，已修。**

### 3.3 回归测试（`tests/test_financial_timeliness_alert.py`，4 条）

1. 告警函数不再进 except、不产生 ERROR 记录；
2. 告警**正文**（`超期天数: 6 天`/`建议行动`/`symbol=全市场`）确实出现在 WARNING 日志里
   ——修好 TypeError 却丢正文等于没修；
3. 缺少 `symbol` 键时仍不抛（覆盖 09-11 那次修复的意图）；
4. **静态护栏**：AST 解析本模块，禁止 stdlib logger 调用使用任意 kwargs（本缺陷类别直接封死）。

## 4. 验证（线上进程内实测，未重启服务）

该 job 的 handler 是**运行期惰性 import**（`application/jobs/data_jobs.py:186`、
`application/services/scheduler_handlers.py:106`），且当前 v2-api 进程（PID 14714，10:56 启动）
尚未执行过该 job —— 故源码修好即生效，无需重启。用线上调度接口直接触发实证：

```console
$ curl -s -X POST http://127.0.0.1:5001/api/scheduler/tasks/318/trigger
{"success":true,"message":"Task 318 dispatched asynchronously",...}

# 触发后的新日志（run_id=3680）：
财报时效性检查开始
financial_timeliness_alert symbol=全市场 expected_date=2026-06-30
📅 财报时效性告警
⚠️ 财务数据超期未更新
当前日期: 2026-09-13 / 预期报告期: 2026-06-30 / 实际报告期: 2026-03-31
披露截止: 2026-08-31 / 超期天数: 6 天
建议行动: 手动执行财务数据更新任务 ...
Job financial_timeliness_check completed: success=True

# 新增日志中错误串出现次数：
$ tail -n +212503 logs/launchd-stdout.log | grep -c "Logger._log() got an unexpected keyword"
0
```

修复前该串在日志中出现 2 次（171028 行 = 09-12 09:00、211937 行 = 09-13 09:00），与事件频次一致。

```console
$ ./venv/bin/python -m pytest tests/test_financial_timeliness_alert.py -q
4 passed in 0.02s
```

## 5. 处置中发现的两个"真问题"（不在本事件范围，交人工/后续）

1. **财报数据确实超期 6 天**：job 的判定是 预期报告期 2026-06-30（Q2），
   实际 `quant.balance_sheets` 最新 `report_date` = **2026-03-31**（Q1），
   披露截止 2026-08-31 + 7 天缓冲 → 09-07 起超期。也就是说：**这条告警本该在 09-10 就送达，
   却因为告警链路本身坏了而没人看见**（三天里只有 "发送失败" 的 error 事件）。
   建议：执行 `python -m infrastructure.jobs.financial_data_update_job --report-date 20260630`（人工确认后）。
2. ~~**告警只有日志通道**~~ → **用户 2026-09-13 确认修复，已完成，见第 6 节**。
   原状：`_send_timeliness_alert` 只写日志（代码注释里的 TODO 说持久化需先建 `system_logs` 表），
   日志没人主动看 → 该 job 的"告警"实际等于没有送达。

另：`quant.scheduler_tasks.last_status` 记的是 `success`——因为异常被业务层吞掉。
这类"任务成功但功能失败"的形态与本次指数采集事件（81d8f56c "跑成功但数据旧"）同源，
本事件只有靠 error 事件台账才露出。

---

## 6. 追加：告警接入 NotificationFacade（2026-09-13，用户确认后执行）

**诉求**：告警只写日志 = 没有送达，必须真投递。

**改动**（`infrastructure/jobs/financial_timeliness_check_job.py`）：

- `_send_timeliness_alert(check_result, facade=None) -> bool`：
  ① 本地日志留痕（标准库 `%s` 惰性格式化，保留）；② 经 **NotificationFacade** 投递
  `send_card(title="📅 财报时效性告警：财务数据超期未更新", content=message, urgency='high')`。
  **禁止**绕过门面直连飞书 SDK/webhook（架构铁律，测试里有 AST 护栏）。
  `facade` 参数可注入，便于测试。
- 投递成功 → `logger.info("...已投递 ... channel=NotificationFacade")`；
  门面返回 False → `logger.error("...投递失败：NotificationFacade 返回 False（日志已留痕但外部渠道未送达）")`
  —— 走 error_events 台账，避免"告警静默失败"。
- `execute()` 的 `result_dict['alert_sent']` 改为**真实投递结果**（原来无论成败都写 True，
  与"任务 success 但功能失败"同源的假成功）。

**验证（线上进程内，restart 后）**

> 注意：本次改动必须先重启才能生效——11:24 那次线上触发已把**旧模块**缓存进 v2-api 进程，
> 直接再触发仍然走旧代码（实测：run_id=3681 日志里没有投递痕迹）。
> 这与"改了源码 ≠ 已生效"是同一类坑，故执行了
> `launchctl kickstart -k gui/501/com.pi-investment.v2-api`（新 PID 62135，health 200）。

```console
$ curl -s -X POST http://127.0.0.1:5001/api/scheduler/tasks/318/trigger
# run_id=3682 日志：
财报时效性检查开始
financial_timeliness_alert symbol=全市场 expected_date=2026-06-30 + 完整告警正文
{"event": "FeishuChannel initialized", "webhook_configured": true, ...}
{"notification_id": "notif_f4d938b820ff43b1", "type": "system_alert", "priority": "high", "event": "发送通知"}
{"notification_id": "notif_f4d938b820ff43b1", "event": "飞书发送成功"}
{"notification_id": "notif_f4d938b820ff43b1", "channel": "feishu", "delivered": true, "event": "通知发送成功"}
财报时效性告警已投递 symbol=全市场 expected=2026-06-30 channel=NotificationFacade

$ ./venv/bin/python -m pytest tests/test_financial_timeliness_alert.py -q
8 passed in 1.11s
```

**新增测试 5 条**（合计 9 条）：投递被调用且 title/urgency/正文正确、门面返回 False 时有 ERROR
可观测且返回 False、门面抛异常不外泄且带栈、模块内禁止直连飞书渠道/裸 webhook、
**"忘记注入 fake facade 必须失败而不是真发消息"**。

### ⚠️ 我自己踩的坑（必须留档）：接入真投递后，单测把消息真发出去了

改完投递、还没给测试加护栏时，本文件里 3 个"只验日志"的老用例调用
`_send_timeliness_alert(SAMPLE)` **没有注入 fake facade** → 走了真实门面 → 两次 pytest
各真发 3 条飞书消息。实测 `public.notification_logs`：今天 11:30:57(×3)、11:31:02–03(×3)、
11:32:33(×3) 共 **9 条**"财报时效性告警"记录（前 6 条可确定来自两次 pytest；
其余 3 条来自线上验证触发，时间戳与进程日志对不齐，未能 100% 归因，按最坏情况披露）。

**护栏**：新增 autouse fixture `_forbid_real_notifications`，把
`application.notification.get_notification_facade` 替换成"报错版"——
任何用例忘记注入 fake，都会**用例失败**而不是骚扰用户；并加了一条自检用例证明该护栏生效。

**教训**：给"只读日志"的功能接上真实外发渠道时，测试的默认姿态必须从"碰真东西"翻转为
"**默认禁止外发、显式注入** fake"，否则 CI/本地跑一遍就会给用户发一串消息。

**未决**：告警会**每个交易日 09:00 重复**直到财报补齐（Q2 报表未入库）。
如需降噪，可加"同一预期报告期只提醒一次 / 按超期天数升级"策略——属策略选择，需人工定。
