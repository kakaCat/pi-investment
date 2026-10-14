---
req_id: REQ-261003150739-b98d
title: 测试策略与验收命令
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4
---

# 测试用例设计（REQ-261003150739-b98d）

## 测试策略（serves: FR-1, FR-2, FR-3, FR-4）

分四层，各自回答一个不同的问题：

- **单测（纯函数）**：`classify()` 对各类 URL 的判定是否正确（零 IO、零 mock）。
- **回归（已知漏点）**：改过的两个测试文件在守卫下跑，**真实外发 = 0** 且断言不变。
- **漂移检测（反向验证）**：人为把桩打错 → 守卫必须让该用例失败（证明它真能抓住，不是摆设）。
- **全量清点**：记账模式下跑一遍测试集，列出仍会真实外发的用例（预期只剩 0 条）。

## 用例清单（serves: FR-1, FR-2, FR-4）

1. `tests/test_false_success_guard.py` 的两条宿主用例：桩打到 `runtime._send_feishu`；
   原断言（`marks[0][0] == 'failed'/'success'`、`'nested boom' in error`）一字不改；
   新增断言：这两个用例的 `NotifyAttempt` 数为 0（连拦截都不该发生——桩在更上游就拦住了）。
2. `tests/e2e/test_daily_orchestrator.py::test_trigger_known_job_returns_success`：
   打桩 `runtime._run_job`；断言 `trigger_job(...)['success'] is True` 且打桩被调用一次（带 job_id）；
   **不得**真正执行 job handler。
3. `classify()` 单测：`AGENT_API_URL` 主机 + `/api/v1/notifications/send` → `'agent'`；
   `FEISHU_WEBHOOK_URL` 主机 → `'feishu'`；`/wake` → `'wake'`；
   普通 URL（`https://example.com/quote`）→ `None`（放行，不得误伤数据源测试）。
4. 守卫回归：`notify_guard.assert_no_real_egress()` 在该文件跑完时通过（`egress == 0`）。

## 反向验证（漂移必须响亮）（serves: FR-4）

人为把第 1 条的桩改回 `alerting._send_feishu`，期望：

- 用例 **失败**（不是静默）；
- 失败信息里带出目标 URL（`…/api/v1/notifications/send`）与"漏桩"指引；
- 真实渠道**仍然收不到**任何消息（拦截先于出网）。

这一条是**人工演练**一次并留证据，不进 CI（它本身是被故意改坏的代码）。

## 验收命令（serves: FR-1, FR-2, FR-3, FR-4）

- `pytest tests/test_false_success_guard.py tests/e2e/test_daily_orchestrator.py -q`
  → 全过；`intercepted=0 egress=0 offenders=[]`。
- `pytest tests/test_freshness_guard.py -q`
  → 全过（该用例自打桩 `pipeline._send_feishu` 并断言告警文本，证明守卫没把正常通知断言打死）。
- `pytest tests/notify_guard* -q`（新增用例文件）
  → 全过（含 `classify` 单测与 `egress == 0` 回归）。
- `QUANTSYS_NOTIFY_GUARD=report pytest tests/ -q`
  → 全量跑完后 `offenders` 为空；非空则逐条处理（打桩或改成显式声明）。
