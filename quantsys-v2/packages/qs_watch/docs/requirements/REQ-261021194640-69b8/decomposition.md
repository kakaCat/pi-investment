# 拆分计划（REQ-261021194640-69b8）

> 目标：把「盯盘执行闭环三接缝」的设计落成可独立开工、可独立验收的任务卡。
> 依据：`docs/requirements/REQ-261021194640-69b8/requirement.md` 与 `design/` 六份设计。
> 口径：每卡一个接口/一个关注点；契约卡先行；验收全部可跑（命令或只读 SQL）。

## 1. 代码层面变更盘点

### 新增

| 文件 | 职责 |
|---|---|
| `packages/qs_trading/qs_trading/application/ports/fill_listener.py` | 成交端口：FillEvent / IFillListener / 注册表 / notify_fill |
| `packages/qs_watch/qs_watch/application/services/watch_engine/news_todo_bridge.py` | 消息命中 → P1 待办 + 唤醒（幂等、不抛错） |
| `infrastructure/persistence/migrations/20261021_watch_todos_evidence.py` | `watch_todos.evidence` 加列 + 部分索引（dry-run / apply） |
| `tests/application/test_fill_port.py` 等新增用例文件 | 端口契约、消息桥、sidecar 窗口、close 联动、执行统计、时区矩阵 |

### 修改

| 文件 | 精确改动 |
|---|---|
| `application/trading/paper_trading_engine.py` | 保留同名符号，改为转发中立端口；`_notify_fill` 调 `notify_fill` |
| `packages/qs_trading/qs_trading/application/services/account_trading_service.py` | `execute_trade` 成交 commit 后发 FillEvent（try/except，不反噬成交） |
| `packages/qs_watch/.../watch_engine/position_lifecycle_service.py` | 补挂止损/止盈时传 `position_state='holding'` |
| `packages/qs_watch/.../watch_engine/news_watch_service.py` | 扫描命中后交给消息桥（可空注入） |
| `packages/qs_watch/.../watch_engine/policy_watch_service.py` | 政策命中持仓板块时交给消息桥 |
| `packages/qs_watch/.../watch_engine/engine.py` | `_run_sidecar` 拆盘中/盘后两段，消息窗口独立 |
| `packages/qs_watch/.../watch_engine/todo_service.py` | `create` 支持证据；`close` 成功后触发规则联动 |
| `packages/qs_watch/.../watch_engine/sla_job.py` | 执行期限巡检 + 时区归一 |
| `packages/qs_watch/.../watch_engine/factory.py` | 装配消息桥、规则联动、成交监听（失败降级） |
| `adapters/inbound/fastapi_app/routes/watch_todo_async.py` | close 透传 `rule_change` |
| `adapters/inbound/fastapi_app/routes/watch_async.py` | 新增 `GET /api/watch/exec/stats` |
| `adapters/outbound/repositories/watch_todo_repository.py` | 证据读写、未收敛去重查询、统计聚合 |
| `infrastructure/persistence/orm/models/watch_todo.py` | 映射 `evidence` 可空列 |

### 删除

无。后台无旧符号删除；旧 import 路径通过转发保持兼容。

## 2. 批次与依赖

| 批次 | 卡 key | 说明 |
|---|---|---|
| B1 契约与数据 | fill-port、evidence-migration、tp-state、todo-close-linkage、sla-deadline | 先定端口、列、关闭契约与期限口径，后续卡只引用 |
| B2 事件源与聚合 | fill-emit、news-bridge、exec-stats | 依赖 B1 的端口/列/时延样本 |
| B3 接入与窗口 | news-hooks、sidecar-window、fill-converge | 依赖 B2 的桥、事件源 |
| B4 装配与验收 | wiring-bootstrap、regression-accept | 依赖全部实现卡 |

依赖方向全部向后（无前向引用）；`depends_on` 使用本计划内的 key。

## 3. 任务表

| 计划 key | 标题 | 阶段 | 端侧 | 依赖 | 验收 | 工作量 | 接口 | 关联 D-x |
|---|---|---|---|---|---|---|---|---|
| fill-port | 建交易包中立成交端口并保留旧路径转发 | implement | backend | 无 | `venv/bin/python -m pytest tests/application/test_fill_port.py -q` 退出码 0；断言注册/注销、旧 import 等价、未注册时 `notify_fill` 返回 False | files 2 / anchors 3 / chars 1200 | IF-1, IF-2 | D-1 |
| evidence-migration | 待办证据列与部分索引 | implement | backend | 无 | 迁移脚本 dry-run 退出码 0；`--apply` 重跑 0 行；`pytest tests/repositories/test_watch_todo_repository.py -q` 退出码 0 | files 3 / anchors 3 / chars 1200 | IF-7, IF-8 | D-2 |
| tp-state | 补挂止损/止盈写持仓状态 | implement | backend | 无 | `pytest tests/application/test_watch_position_lifecycle.py -q` 退出码 0；新用例断言补挂后 `position_state='holding'` 且下一拍参与求值 | files 2 / anchors 2 / chars 600 | — | D-2 |
| todo-close-linkage | 关闭待办接规则变更联动 | implement | backend | 无 | `pytest tests/application/test_rule_change_linkage.py tests/application/test_watch_todo_close_rule_change.py -q` 退出码 0；审计 1 行且 `trigger_id` 非空；重复关闭 409 | files 4 / anchors 3 / chars 1400 | IF-3 | D-1 |
| sla-deadline | 执行期限巡检与时区归一 | implement | backend | 无 | `pytest tests/application/test_sla_job.py -q` 退出码 0；期限前 0 条、期限后 1 条、重复 tick 仍 1 条、不写 expired | files 2 / anchors 4 / chars 1200 | IF-6 | D-2 |
| fill-emit | 真实成交落库后发事件 | implement | backend | fill-port | `pytest tests/application/test_account_trade_fill_callback.py -q` 退出码 0；断言卖出事件 `action='sell'`、`trade_id` 非空；回调抛错时成交仍成功 | files 2 / anchors 3 / chars 1200 | IF-2 | D-1 |
| news-bridge | 消息→P1 待办桥（critical 建单 + 唤醒） | implement | backend | evidence-migration | `pytest tests/application/test_news_todo_bridge.py -q` 退出码 0；critical 建 1 条、soft 0 条、重复扫描不新增、方法不抛错 | files 2 / anchors 4 / chars 1400 | IF-5 | D-3 |
| exec-stats | 执行闭环统计端点 | implement | backend | fill-emit | `pytest tests/api/test_watch_exec_stats.py -q` 退出码 0；空数据全 0；三态计数与台账一致；p50/p95 可读 | files 3 / anchors 3 / chars 1200 | IF-4 | D-2 |
| news-hooks | 新闻与政策扫描接入消息桥 | implement | backend | news-bridge | `pytest tests/application/test_news_watch_service.py tests/application/test_policy_watch_service.py -q` 退出码 0；critical 建单、soft 只发卡；桥未注入行为不变 | files 4 / anchors 3 / chars 1200 | IF-5 | D-3 |
| sidecar-window | sidecar 拆盘中/盘后，盘后消息可扫 | implement | backend | news-bridge | `pytest tests/application/test_watch_sidecar_window.py -q` 退出码 0；16:30 扫描执行、回填不重复、非交易日不跑 | files 2 / anchors 3 / chars 1000 | IF-6 | D-3 |
| fill-converge | 成交收敛端到端场景 | test | backend | fill-emit | `pytest tests/scenarios/test_watch_fill_converge.py -q` 退出码 0；清仓四收敛、买入转持有、部分不收敛、重复幂等、读失败 fail-closed | files 1 / anchors 5 / chars 1000 | IF-1, IF-2 | D-1 |
| wiring-bootstrap | 组合根装配与降级开关 | integrate | backend | fill-emit, news-bridge, todo-close-linkage, sla-deadline | `pytest tests/application/test_fill_sync_factory_wiring.py tests/application/test_watch_factory_news_bridge.py -q` 退出码 0；未注入=旧行为；装配失败不阻断引擎启动 | files 2 / anchors 3 / chars 900 | IF-1, IF-5 | D-1, D-3 |
| regression-accept | 回归与生产只读核查 | test | backend | 全部实现卡 | `venv/bin/python -m pytest tests -k "watch or fill or todo or trading" -q` 退出码 0（存量 2 例失败先定性并记录）；三条只读 SQL 有结果 | files 1 / anchors 4 / chars 800 | IF-1～IF-8 | D-2 |

## 4. 接口清单 ↔ 接收卡 key

| 接口 id | 接口 | 接收卡 key |
|---|---|---|
| IF-1 | 成交回调协议 | fill-port、fill-converge |
| IF-2 | 成交通知函数 | fill-port、fill-emit |
| IF-3 | 待办关闭（rule_change） | todo-close-linkage |
| IF-4 | 执行闭环统计 | exec-stats |
| IF-5 | 消息→待办桥 | news-bridge、news-hooks |
| IF-6 | sidecar 盘中/盘后分段 | sidecar-window、sla-deadline |
| IF-7 | 待办证据数据契约 | evidence-migration、news-bridge |
| IF-8 | 迁移脚本 CLI | evidence-migration |

## 5. 容量核算

口径 `detailUnits = files + anchors×0.5 + chars/2000`，容量 16 DU。

| 卡 | files | anchors | chars | DU |
|---|---|---|---|---|
| fill-port | 2 | 3 | 1200 | 4.1 |
| evidence-migration | 3 | 3 | 1200 | 5.1 |
| tp-state | 2 | 2 | 600 | 3.3 |
| todo-close-linkage | 4 | 3 | 1400 | 6.2 |
| sla-deadline | 2 | 4 | 1200 | 4.6 |
| fill-emit | 2 | 3 | 1200 | 4.1 |
| news-bridge | 2 | 4 | 1400 | 4.7 |
| exec-stats | 3 | 3 | 1200 | 5.1 |
| news-hooks | 4 | 3 | 1200 | 6.1 |
| sidecar-window | 2 | 3 | 1000 | 4.0 |
| fill-converge | 1 | 5 | 1000 | 4.0 |
| wiring-bootstrap | 2 | 3 | 900 | 4.0 |
| regression-accept | 1 | 4 | 800 | 3.4 |

全部 ≤ 16 DU，无需切分或标红。

## 6. 边界与不做

- 不做 v2 自动下单；不改 `IntradayMonitor` 行为（D-1）。
- 不做交易计划实体、盘中实时资金流、减仓数量化（D-2）。
- 不改表语义（只加一列与一个部分索引）；无删除动作。
- 不改既有待办终态枚举与 HTTP 响应字段（additive）。

## 7. 提交与批准

- 本计划经人批准后落库任务卡并进入实施；未批准不落库。
- 批准后可改：重新提交本文件并重新批准（旧批准作废）。
