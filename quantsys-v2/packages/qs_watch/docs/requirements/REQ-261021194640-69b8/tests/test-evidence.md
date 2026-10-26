# 验收证据（REQ-261021194640-69b8 · 回归与生产只读核查）

> 对应任务卡 `t-f9a9b3`。本文件是回归与生产核查的**可复核证据**，随验收材料提交。

## 1. 全量回归

命令（仓库根）：

```bash
venv/bin/python -m pytest tests -k "watch or fill or todo or trading" -q
```

读数：`2 failed, 1195 passed`，耗时约 331s。

失败两例均为**存量基线**（实现开始前已复现，与本次改动无关）：

- `tests/application/test_watch_t12_todo_creation.py::test_p2_trigger_creates_todo_l1_due_day_close`
- `tests/application/test_watch_t12_todo_creation.py::test_deduped_trigger_does_not_create_todo`

定性：两例用 `scope=sector` 的 P2 规则断言建待办，而市场级规则自 2026-10-20 起走
`market_watch_service` 独立通道（不进个股 tick），属**旧用例未随路由同步**，非本次三条接缝引入。

## 2. 新增/修改卡片的专项读数

| 卡 | 命令 | 读数 |
|---|---|---|
| 成交端口 | `pytest tests/application/test_fill_port.py -q` | 24 passed |
| 成交发包 | `pytest tests/application/test_account_trade_fill_callback.py -q` | 4 passed |
| 成交收敛场景 | `pytest tests/scenarios/test_watch_fill_converge.py -q` | 5 passed |
| 消息桥 | `pytest tests/application/test_news_todo_bridge.py -q` | 6 passed |
| 扫描接入 | `pytest tests/application/test_news_hooks.py -q` | 6 passed |
| 盘后窗口 | `pytest tests/application/test_watch_sidecar_window.py -q` | 5 passed |
| 关闭联动 | `pytest tests/application/test_watch_todo_close_rule_change.py -q` | 8 passed |
| 执行期限 | `pytest tests/application/test_sla_job.py -q` | 42 passed |
| 统计端点 | `pytest tests/api/test_watch_exec_stats.py -q` | 5 passed |
| 装配 | `pytest tests/application/test_watch_factory_news_bridge.py -q` | 3 passed |

## 3. 生产只读核查（未写库、未重启）

| 检查 | 读数 | 解释 |
|---|---|---|
| `SELECT count(*) FROM quant.watch_triggers WHERE detail ? 'exec'` | **0** | 新回写链未上线（生产进程仍跑旧代码） |
| `SELECT count(*) FROM quant.watch_todos WHERE evidence IS NOT NULL` | **0** | 消息待办尚未产生（同上） |
| `SELECT count(*) FROM quant.watch_todos WHERE terminal IS NULL` | **3** | 未收敛待办存量 |
| `WatchTodoRepository().exec_stats()` | executed=0 / declined=22 / unresolved=2 / timeout=146 / 时延样本=0 | 统计聚合可读；时延为 0 因尚无 agent 成交回写 |

## 4. 生产生效条件

生产 5001 进程启动于 19:04（旧代码），新链路需一次重启：

```bash
launchctl kickstart -k gui/501/com.pi-investment.v2-api
```

重启后观察三项：`watch_triggers.detail` 出现 `exec` 键；盘后日志出现消息扫描轮次；
`GET /api/watch/exec/stats` 可读且与 `watch_todos` 台账一致。

## 5. 遗留（已登记，不阻塞本期）

- 既有 `due_at` 提醒链的 naive 写入口径未在本期修（执行期限链已绕开该口径，改用库端 `created_at`）。
- 消息待办去重按未收敛待办扫描实现（复用 `list_pending`），未新增专用查询；索引已就绪。


## 测试覆盖的任务卡

covers: t-c6c5d2
covers: t-0846ee
covers: t-c18a41
covers: t-e95a2a
covers: t-e29f67
covers: t-a5fa64
covers: t-27e8c7
covers: t-b8d5ae
covers: t-88d4da
covers: t-3ef50b
covers: t-2ff7ca
covers: t-e416b7
covers: t-f9a9b3
covers: t-1c3597
covers: t-f2474a
covers: t-e1eb49
covers: t-7e4e44
covers: t-947421
covers: t-902bf1
covers: t-c1ce88
covers: t-2932b9
covers: t-552104
covers: t-c41448
covers: t-ec9d80
covers: t-66833a
covers: t-da557b
covers: t-46c354
covers: t-91a8b2
covers: t-eb06ad
covers: t-c573f5
covers: t-a8d1da
covers: t-7d1677
covers: t-627a70
