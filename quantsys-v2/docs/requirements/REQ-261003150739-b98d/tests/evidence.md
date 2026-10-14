# 测试证据 · REQ-261003150739-b98d

**日期**：2026-10-03 ｜ **机器**：同一台 ｜ **Python**：venv/bin/python（3.13.14）｜ **pytest**：9.1.1

---

## 1. 交付前的"病灶"（改前基线，可复现）

用把 `NotificationFacade` 换成计数器的临时插件跑测试，数**真实投递**：

| 跑的用例 | 真实投递 | 内容 |
|---|---|---|
| `tests/test_false_success_guard.py`（整文件） | **4** | 开始/失败/开始/完成，均 `fake_job` |
| `test_daily_orchestrator.py -k trigger_known` | **2** | 开始/完成，`watch_rule_health`（且真跑了 handler） |

## 2. 逐条验收命令与输出

```bash
# FR-1 + FR-2 + 回归（守卫默认 fail 模式）
pytest tests/test_false_success_guard.py tests/e2e/test_daily_orchestrator.py \
       tests/test_freshness_guard.py tests/test_trading_day_guard.py -q
# → 64 passed（会话汇总 intercepted=0 egress=0 offenders=[]）

# 守卫单测（classify 四类 + 误伤回归 + fail 默认锁）
pytest tests/test_notify_guard.py -q            # → 15 passed

# 单点复核
pytest tests/test_false_success_guard.py -q     # → 17 passed（改前真实投递 4 → 今 0）
pytest tests/e2e/test_daily_orchestrator.py -k trigger_known -s 2>&1 | grep -c inprocess_job_start
# → 0（改前为 2，且真跑 watch_rule_health）

# 回滚开关
QUANTSYS_NOTIFY_GUARD=off pytest tests/test_false_success_guard.py \
       tests/e2e/test_daily_orchestrator.py tests/test_freshness_guard.py -q
# → 36 passed（守卫不安装，行为回到改造前）
```

## 3. 反向验证（漂移必须响亮）

临时探针复刻 2026-10-02 的旧漏点（桩打回 `alerting`），原文输出：

```
notify-guard intercepted=2 egress=0 offenders=['tests/test_drift_probe_tmp.py::test_drift_to_alerting_is_caught']
本用例发生真实通知外发 2 次（agent: POST http://localhost:8080/api/v1/notifications/send; …）
——测试漏桩；请把桩打在实现所在模块（见 docs/requirements/REQ-261003150739-b98d/design/interfaces.md）
1 failed, 1 error
```

要点：**用例红了，但 egress 仍为 0**——拦截先于出网，用户收不到任何东西。
探针文件已删除（`ls tests/test_drift_probe_tmp.py` → No such file）。

## 4. 全量清点（report 模式，整套 `pytest tests/`）

| 轮次 | intercepted | offenders | 全量结果 | 触发的原因 |
|---|---|---|---|---|
| ① 初版判据（只比主机名） | 102 | 58 | 25 failed | 守卫误伤：`127.0.0.1` 任意端口都被当成通知外发 |
| ② 判据改 authority（主机+端口） | 3 | 3 | **0 failed** | 只剩 `trading_day_guard` 的顺序相关真漏点 |
| ③ 摘掉残留 `_degraded_alert_sink`（最终） | **0** | **0** | **6154 passed / 0 failed** | — |

三轮耗时分别 210s / 218s / 266s；每轮都是 `QUANTSYS_NOTIFY_GUARD=report`（只拦截记账、不判失败），
以"先清点、后收紧"的顺序验证默认 fail 模式不会误伤既有用例。

**3 个 errors** 来自 `tests/daemon/test_daemon_integration.py`（`FileNotFound`），
在第一轮与第三轮**完全一致**，与本需求无关。

## 5. 任务覆盖对照（covers 标注）

每条任务（父卡 + 子卡）对应的验收/测试证据如下；命令与输出见上文第 2 节。

- covers: t-0cb72d — FR-1 打桩点：`pytest tests/test_false_success_guard.py -q` → 17 passed、真实投递 4 → 0
- covers: t-821cbb — 该卡研发段：桩改到 `daily_jobs.runtime._send_feishu`（`git diff` 可见）
- covers: t-91bf18 — 该卡联调段：同文件其余 16 条用例共用夹具一起跑通
- covers: t-0ff3c9 — 该卡复核段：diff 仅桩目标 2 处 + 注释，断言零改动
- covers: t-77768c — 该卡测试段：17 passed；老桩反例仍为 2 次真实调用
- covers: t-59908f — FR-2 e2e：`pytest tests/e2e/test_daily_orchestrator.py -q` → 15 passed
- covers: t-e8c8e2 — 该卡研发段：用例改为打桩 `runtime._run_job` 并断言派发
- covers: t-568226 — 该卡联调段：`trigger_job` → `_run_job` 调用链在本模块内，桩覆盖完整
- covers: t-5e56b0 — 该卡复核段：原 `trigger_job` 返回契约断言保留
- covers: t-927202 — 该卡测试段：`grep -c inprocess_job_start` → 0（改前 2）
- covers: t-47c844 — FR-3 守卫：`pytest tests/test_notify_guard.py -q` → 15 passed、整套 `egress=0`
- covers: t-48d78d — 该卡研发段：`tests/notify_guard.py` + `conftest.py` 接线（report 模式）
- covers: t-7dffbf — 该卡联调段：通知相关 8 个文件 153 passed，既有打桩方式零改动
- covers: t-7321dc — 该卡复核段：非通知 URL 原样放行（误伤回归 2 条）
- covers: t-60761f — 该卡测试段：`QUANTSYS_NOTIFY_GUARD=off` 时守卫不安装
- covers: t-bfaab6 — FR-4 回归锁：默认 fail + 反向验证（用例红、URL 打出、egress 0）
- covers: t-290c47 — 该卡研发段：`DEFAULT_MODE` 切 `fail`、三条回归锁
- covers: t-a8df02 — 该卡复核段：复刻旧漏点探针 → 失败原文（第 3 节），探针已删
- covers: t-6dc8f2 — 该卡测试段：四文件 64 passed；off 开关重跑仍全过
