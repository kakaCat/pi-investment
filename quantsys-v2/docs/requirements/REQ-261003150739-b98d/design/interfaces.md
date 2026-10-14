---
req_id: REQ-261003150739-b98d
title: 守卫接口与打桩点契约
doc: design/interfaces
serves: FR-1, FR-2, FR-3, FR-4
---

# 接口设计（REQ-261003150739-b98d）

## 守卫模块 API（serves: FR-3）

新增 `tests/notify_guard.py`（**测试专用**：不被任何生产模块导入，故不进生产依赖图）。

- `classify(url: str) -> str | None`
  纯函数，零 IO：返回 `'agent' | 'feishu' | 'wake' | None`。`None` = 与通知无关，放行。
- `install_notify_guard() -> GuardHandle`
  幂等安装：把全局 `requests.post` / `requests.get` 换成包装器并保留原函数；重复调用返回同一 handle。
- `GuardHandle.uninstall() -> None`
  还原原始 `requests.post/get`（会话结束自动调用）。
- `GuardHandle.attempts() -> list[NotifyAttempt]`
  本次会话的全部命中记录（含被拦下的）。
- `GuardHandle.real_egress_count() -> int`
  **真正发出去的**通知请求数——结构上恒为 0（拦截发生在调用真实函数之前），供回归断言。
- `GuardHandle.assert_no_real_egress() -> None`
  不为 0 时抛 `AssertionError`（带 URL 与用例 nodeid）。

conftest 侧接口：

- 会话级 fixture `notify_guard` → `GuardHandle`（供回归用例读取与断言）；
- `pytest_sessionfinish` 打印一行汇总：`intercepted=N egress=0 offenders=[nodeid…]`；
- 环境开关 `QUANTSYS_NOTIFY_GUARD`：`off` = 完全不安装；`report` = 记账模式（不判失败）；未设 = 判失败模式。

## 打桩点契约（serves: FR-1, FR-2）

**规则**：桩打在**被调函数所在模块**，不是符号来源模块、不是转发壳。

- 失败态通知发送：`adapters.inbound.fastapi_app.daily_jobs.runtime._send_feishu`
  （`runtime._run_job` 在运行时查自己模块的全局名，改 `alerting` 或 `daily_jobs_bootstrap` 都无效）。
- 进程内宿主任务执行：`adapters.inbound.fastapi_app.daily_jobs.runtime._run_job`
  （e2e 手动触发用例打它 → 不跑真实 handler，也不产生任何通知）。

**反例清单**（写上以免下次再选错）：`alerting._send_feishu`、`daily_jobs_bootstrap._send_feishu`
—— 这两个名字**存在**（所以打桩不报错），但**不是被调用的那个**，属"静默失效"。

## 错误语义（serves: FR-3, FR-4）

- **拦截响应**（命中接收端时返回给调用方的合成对象）：
  `status_code=200`、`json() -> {"success": true, "code": 0, "StatusCode": 0}`、`text=''`、`headers={}`。
  语义：渠道视为"发送成功"，**上层的成功/失败判定与拦截前一致**（守卫不改变被测行为）。
- **用例级失败**（判失败模式下，某用例发生未声明外发时 teardown 抛错）：
  `本用例发生真实通知外发 N 次（agent: POST http://…/api/v1/notifications/send）——测试漏桩；
   请把桩打在实现所在模块（见 docs/requirements/REQ-261003150739-b98d/design/interfaces.md）`
- **会话级汇总**：`intercepted=N egress=0 offenders=[…]`；`offenders` 非空时退出码非 0。
- **fail-open 边界**：包装器自身抛异常时**不得**吞掉调用（要让被测代码看到真实异常），
  但记账要留下标记——守卫出错不能变成"静默放行"。
