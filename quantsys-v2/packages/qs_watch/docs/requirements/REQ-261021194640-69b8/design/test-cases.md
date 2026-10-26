---
title: 盯盘执行闭环三接缝 测试策略与用例矩阵（REQ-261021194640-69b8）
status: draft
owner: agent（本窗口 · design-tests）
reviewers: 投资人（验收口径）、agent（执行者）
prd: docs/requirements/REQ-261021194640-69b8/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8
created: 2026-10-21
updated: 2026-10-21
---

# 盯盘执行闭环三接缝 测试策略与用例矩阵（REQ-261021194640-69b8）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

> 本文是 Design Review 的**评审对象**：只回答「怎么证明三条接缝真的接上了、坏了怎么发现」，不复述 PRD。
> 范围口径与裁定见 `docs/requirements/REQ-261021194640-69b8/requirement.md` 与 RFC 017；本文所有用例都写到可执行命令一级。

## 摘要  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **问题**：三条接缝（成交回写、消息投递、待办闭环）当前都没有自动收敛路径，也没有能证伪它们的用例——「止损喊了没人卖」在生产上无法被测试拦住。
- **方案**：以**端口假件单测**为底座、**`tests/scenarios/` 场景 e2e** 为闭环证据、**生产只读核查**为事后对账，把 39 条用例按三条接缝分组，每条固定「步骤 → 断言 → 可执行命令」三段式，并显式标注当前应为红（缺陷复现）的用例。
- **影响面**：新增 6 个测试文件（端口、成交通知点、消息待办、sidecar 窗口、待办联动、执行统计）、扩展 3 个既有文件；判据全部落在库内台账字段与接口响应，不依赖外部网络与真实券商。

## 背景与问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 需求来源  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 审计：`execute_trade` 成交后零通知（`qs_trading/.../account_trading_service.py:151`），生产 `watch_triggers.detail` 含执行明细 0 行，P0 待办 #107 悬空 | 用「卖出清仓 → 待办/触发/规则/状态四收敛」e2e 钉死结局，并补部分成交、重复成交两条边界 |
| FR-2 | 用户裁定 D-1/D-2：agent 下单后系统要秒级知道持仓变了，不能重复喊建仓 | 买入成交 → `position_state='holding'` + 状态门跳过 entry + 止损照常求值，三条断言同拍 |
| FR-3 | 审计：`news_alert` 只进回执发送，不建待办、不唤醒；用户裁定 D-3 只对 critical 建单 | critical 命中持仓标的/板块 → P1 待办 + 唤醒各 1；soft → 待办 0；重复扫描不增 |
| FR-4 | 审计：sidecar 仅在交易时段运行（`engine.py:740-744`），生产今日最后一轮扫描 14:52 | 时钟设为交易日 16:30 → 消息扫描执行，回填/生命周期等日频任务不重复执行 |
| FR-5 | 审计：`RuleChangeLinkage` 全仓仅测试引用，零生产调用；规则路由不写审计 | 关闭为 `ignored` → 规则字段变化 + `watch_rule_changes` 新增 1 行且 `trigger_id` 非空；重复关闭 409 |
| FR-6 | 审计：执行期限环境变量零消费；`sla_job` 时区 +8h 致生产 3 分钟连发 3 张超时卡 | 时区矩阵单测 + 期限前 1 分钟 0 / 后 1 分钟 1 / 重复 tick 仍 1 的确定性用例 |
| FR-7 | 审计：执行统计端点不存在；现有触发统计先取 200 行再过滤，今日 232 条必截断 | `GET /api/watch/exec/stats` 三态计数与 p50/p95，与 `watch_todos` 同口径 SQL 逐项相等 |
| FR-8 | 审计：日频补挂不写 `position_state`，DB 默认无持仓 → 退出族规则被状态门跳过（潜在漏保护） | 补挂后规则 `position_state='holding'` 且下一拍参与求值；不写状态时该用例先红 |

### 现状与代价  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 今天要证明「成交后系统知道了」，只能人去生产库捞 `watch_triggers.detail` 与 `watch_todos.terminal`，一次对账 15–30 分钟，且仍分不清「没执行」与「没回写」。
- 成交回写没有失败路径测试：回调抛错会不会反噬成交，只能靠代码评审口头保证——这是资损级风险，必须用注入用例替代口头保证。
- 超时口径靠环境变量与机器时区，历史上已因 +8h 偏移在生产连发 3 张卡；没有时区矩阵用例，同一缺陷必然复发。
- 消息投递与待办联动没有任何用例覆盖，`RuleChangeLinkage` 属于「已实现、零调用」的典型死线，改动它没有回归网。

### 为什么是现在  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

三条接缝共享同一批台账字段（`watch_todos` / `watch_triggers` / `watch_rule_changes`），任何一条先上生产而没有用例，后两条的验收都会被「数据口径不一致」污染。现在不建矩阵，后面每接一条都要重做一次对账口径；且先红用例本身就是缺陷复现清单，越晚写越难定位回归来源。

## 目标与非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 每条 FR 至少 1 条正向 + 1 条失败/边界用例，且断言可机器判定（字段取值、计数、退出码），不写「行为正确」这类无可证伪表述。
- 三条接缝各自闭环可见：成交回写（买入转持有、卖出清仓收敛、部分成交不收敛、重复成交幂等、回调异常不影响成交）、消息投递（critical 建 P1 + 唤醒、soft 不建、重复幂等、盘后 16:30 可扫、非交易日不扫）、待办闭环（不执行改规则 + 审计、超时时区矩阵、期限幂等、并发关闭 409、exec/stats 计数对账）。
- 全部用例可在本机执行：单测与场景 e2e 不依赖外部网络；生产只读核查只允许 SELECT。
- 先红清单（缺陷复现）与 FR 一一绑定，里程碑出口以「红转绿」判定，而不是以「用例写完」判定。
- 判据字段固定：`watch_todos.terminal` / `action_kind` / `evidence`、`watch_triggers.disposition` / `detail.exec`、`watch_rules.position_state` / `enabled`、`watch_rule_changes.trigger_id`、`/api/watch/exec/stats` 响应体。

### 非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 不做故障注入平台与混沌工程：回调异常只用进程内注入（monkeypatch）覆盖，不引入新框架。
- 不改生产数据：生产侧只有只读 SQL 核查，不提供修数脚本，也不在本期做自动对账任务。
- 不做前端/卡片渲染断言：通知落点只断言「被调用一次 + 参数含关键字段」，不校验飞书文案与排版。
- 不覆盖券商真实下单与真实成交：闭环以成交事实（`FillEvent`）为起点，真实券商链路由交易包自身测试负责。
- 不做性能压测：只记录单测与 e2e 的耗时预算，不设吞吐指标（本期无新增热路径查询）。
- 不重写既有 34 条 `sla_job` 用例与 35 条 `fill_sync` 用例，只做增量与兼容性断言。

## 方案总览  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

**一句话方案**：把三条接缝拆成三层证据——端口假件单测证明**语义**、`tests/scenarios/` 场景 e2e 证明**接线**、生产只读核查证明**口径**；每条用例只断言一个可核验事实，先红用例单独成清单，按里程碑转绿。

```text
tests/application/test_fill_listener_port.py      ── 端口形状/注册位/旧路径兼容（假件）
tests/application/test_account_trading_fill_notify.py ── 成交落库后 notify_fill（假 port）
tests/application/test_watch_news_todo.py         ── critical/soft/去重（假仓储 + 假时钟）
tests/application/test_watch_sidecar_window.py    ── 16:30/非交易日（假时钟 + 假服务）
tests/application/test_watch_todo_close_linkage.py ── close + rule_change（假仓储 + 假 linkage）
tests/api/test_watch_exec_stats.py                ── /exec/stats 计数与时延（假仓储 / quant_test）
tests/scenarios/test_watch_exec_loop_e2e.py       ── 三态闭环端到端（既有，扩展）
tests/scenarios/test_watch_news_todo_e2e.py       ── 消息→待办→唤醒端到端（新增）
tests/migration/test_watch_todos_evidence_column.py ── evidence 列 + 部分索引（quant_test）
```

### 测试分层与命令约定  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

命令一律在**仓库根 `quantsys-v2/`** 执行（`pytest.ini` 与 `tests/` 都在根），解释器取根 `venv/bin/python`；本文落在 `packages/qs_watch/docs/` 只是文档归属，不是命令工作目录。

| 层级 | 范围 | 替身与事实源 | 命令入口 | 何时跑 |
|---|---|---|---|---|
| 单测（端口假件） | 端口语义、通知调用点、消息分级与去重、关闭联动、SLA 期限、sidecar 窗口、统计计算 | 假仓储（todo/trigger/rule/receipt）、假时钟、假通知器、假唤醒器；无 DB、无网络 | `venv/bin/python -m pytest tests/application/test_watch_news_todo.py -q` | 每次提交 |
| 场景 e2e | 组合根装配下的三态闭环与消息投递 | 只替换出口与取数（notifier/waker/repo/position），判定与编排全走生产代码 | `venv/bin/python -m pytest tests/scenarios/ -q` | 每次提交（CI 必跑） |
| 生产只读核查 | 成交留痕、盘后扫描轮次、统计与台账同口径 | 真实库 `quant_investment`，只允许 SELECT | `psql "$PGDSN" -c "<SELECT ...>"`（人执行） | 发布当日 + 连续 5 个交易日 |

**用例编号规则**：`TC-FILL`（成交回写）/`TC-PORT`（端口契约）/`TC-NEWS`（消息投递）/`TC-LOOP`（待办闭环）/`TC-SLA`（执行期限）/`TC-STAT`（统计）/`TC-DB`（数据迁移）/`TC-REG`（回归与生产核查）。编号不复用，删除的用例空号留白。

**每条用例的固定五段**：构造（种子事实）→ 步骤 → 断言（字段取值 / 计数 / 退出码）→ 命令 → 现状。**现状**取三种值：`基线已绿`（既有实现已满足）/`先红（缺陷复现）`（当前必然失败，转绿即验收）/`半绿`（既有单测已绿，新增接线段先红）。

### 用例矩阵总表  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 用例组 | 条数 | 覆盖 FR | 先红条数 |
|---|---|---|---|
| TC-FILL（成交回写） | 8 | FR-1, FR-2 | 1（成交通知点） |
| TC-PORT（端口契约） | 4 | FR-1, FR-2 | 3 |
| TC-NEWS（消息投递） | 8 | FR-3, FR-4 | 8 |
| TC-LOOP（待办闭环） | 7 | FR-5, FR-8 | 4 |
| TC-SLA（执行期限） | 4 | FR-6 | 4 |
| TC-STAT（闭环统计） | 4 | FR-7 | 4 |
| TC-DB（数据迁移） | 1 | FR-3, FR-7 | 1 |
| TC-REG（回归与生产核查） | 3 | 全文 | 0 |
| **合计** | **39** | FR-1～FR-8 | **25** |

### 接缝① 成交回写用例  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-FILL-01 卖出清仓 → 待办/触发/规则/状态四收敛  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：场景 e2e（正向）
- **构造**：`watch_rules(exit_stop, level=P0, linked_account='agent', position_state='holding', enabled=True)` + 未收敛 `watch_todos(action_kind='trade', level='P0')` + `simulation_positions.shares_total=1000`
- **步骤**：引擎触发记 `watch_triggers` → 注入 `FillEvent(action='sell', shares=1000, price=11.42, trade_id=8812)` → 读四处台账
- **断言**：`todos.terminal=='handled'`；`todos.action_kind=='trade'`；`triggers.disposition=='handled'`；`triggers.detail['exec']['trade_id']==8812` 且 `latency_sec>=0`；`rules.position_state=='none'`；exit 族规则 `enabled is False`
- **命令**：`venv/bin/python -m pytest tests/scenarios/test_watch_exec_loop_e2e.py -q -k "F1_fill_converges_exec_loop_end_to_end"`
- **期望**：退出码 0；失败时首条断言即定位到哪个收敛没发生
- **现状**：基线已绿（`tests/scenarios/test_watch_exec_loop_e2e.py:354`）

#### TC-FILL-02 买入成交 → 秒级转持有，入场被状态门挡、止损照常  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向）
- **构造**：同标的 `entry` 与 `exit_stop` 各一条规则，`position_state='none'`；持仓表 `shares_total=0`
- **步骤**：注入 `FillEvent(action='buy', shares=500)` → 断言规则状态 → 下一拍 `evaluate` 
- **断言**：`rules.position_state=='holding'`；下一拍 entry 规则未进入取价（`quote_calls` 不含该 symbol）；`exit_stop` 照常求值
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_position_state_branch.py -q -k "holding_blocks_entry or holding_keeps_stop"`
- **期望**：退出码 0；断言 `rule.position_state == 'holding'` 与分支表逐格一致
- **现状**：基线已绿

#### TC-FILL-03 部分成交不收敛（边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：持仓 `shares_total=1000`，待办未收敛
- **步骤**：注入 `FillEvent(action='sell', shares=400)` → 再查待办与规则
- **断言**：`todos.terminal is None`；`position_state=='holding'`；结果 `status=='partial'`；无 `detail.exec` 时延写入
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_sync_service.py -q -k "partial_sell_does_not_converge"`
- **期望**：退出码 0
- **现状**：基线已绿

#### TC-FILL-04 重复成交号幂等：只收敛一次，时延只写一次  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（失败/边界·幂等）
- **构造**：已收敛待办 + `detail.exec` 已有 `latency_sec=47`
- **步骤**：同一 `trade_id=8812` 的事件再投递两次
- **断言**：`detail.exec` 不被覆盖（仍 47）；`todos.closed_at` 不变；异常不抛出；审计写入计数不增
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_sync_service.py -q -k "duplicate_fill_does_not_reconverge or preexisting_exec_detail_is_not_overwritten"`
- **期望**：退出码 0
- **现状**：基线已绿

#### TC-FILL-05 回调异常不影响成交（失败注入）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（失败路径）
- **构造**：注册一个 `on_fill` 必抛 `RuntimeError` 的监听器
- **步骤**：走 paper 引擎买卖各一次（`_notify_fill` 路径）
- **断言**：成交落库成功（trade 行存在、持仓变动）；异常被吞；日志含回调失败标记；`fill_listener` 仍为已注册对象
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_sync_service.py -q -k "callback_exception_does_not_break"`
- **期望**：退出码 0
- **现状**：基线已绿

#### TC-FILL-06 `execute_trade` 成交落库后调用 `notify_fill`（缺陷复现）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向 + 失败注入）
- **构造**：`AccountTradingService` + 假 session（commit 计数）+ 注册假 `IFillListener`；`_auto_record_decision` 返回 `audit_id='dec-9'`
- **步骤**：`execute_trade(action='sell', ...)` → 检查调用时序与 event 字段 → 再让监听器抛错重跑一次
- **断言**：`commit` 已被调用后才见到 `on_fill`；event 的 `symbol/account_name/action/shares/price/trade_id/decision_audit_id/filled_at` 与落库事实一致；监听器抛错时 `execute_trade` 仍返回成功且 trade 行存在
- **命令**：`venv/bin/python -m pytest tests/application/test_account_trading_fill_notify.py -q`
- **期望**：退出码 0；`calls[0].decision_audit_id == 'dec-9'`，降级场景为 `None` 且不虚报
- **现状**：先红（`execute_trade` 零通知，见审计 `account_trading_service.py:151`）

#### TC-FILL-07 持仓读数故障 → fail-closed：不动规则、不误收敛（失败）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（失败路径）
- **构造**：持仓仓储 `read` 抛异常（`degraded=True`）
- **步骤**：注入一条卖出清仓事件
- **断言**：`position_state` 保持原值；待办仍 `terminal is None`；规则仍 `enabled is True`；`errors` 计数 1；无审计写入
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_sync_service.py -q -k "position_read_failure_touches_nothing"`
- **期望**：退出码 0
- **现状**：基线已绿

#### TC-FILL-08 非 P0 / 非 trade 待办不被成交误收敛（边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：P1 `action_kind='rule_change'` 待办 + P0 `action_kind=None` 待办各一条
- **步骤**：注入卖出清仓事件
- **断言**：两条待办 `terminal is None`；仅 P0 `action_kind='trade'` 那条被收敛（另建对照组）
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_sync_service.py -q -k "only_p0_trade_todos_are_converged"`
- **期望**：退出码 0
- **现状**：基线已绿

### 接缝① 端口契约用例（交易包中立端口）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-PORT-01 中立端口形状与 `FillEvent` 字段  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（契约）
- **构造**：从 `qs_trading/application/ports/fill_listener.py` import `FillEvent`、`IFillListener`、`register_fill_listener`、`get_fill_listener`、`unregister_fill_listener`、`notify_fill`
- **步骤**：实例化 `FillEvent` 必填字段 → 断言 `IFillListener` 是 `runtime_checkable` 协议且含 `on_fill`
- **断言**：字段集与 RFC 017 §2.1.4 一致（含 `source` 默认值）；`notify_fill` 可调用；缺 `on_fill` 的对象注册抛 `TypeError`
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_listener_port.py -q -k "shape or fields"`
- **期望**：退出码 0
- **现状**：先红（端口现定义在 `application/trading/paper_trading_engine.py`，中立端口模块尚未建立）

#### TC-PORT-02 注册位：register / get / unregister 与缺省 no-op  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（契约）
- **构造**：`autouse` fixture 在用例前后 `unregister_fill_listener()`
- **步骤**：未注册时 `notify_fill(event)` → 再注册假监听器 → 再注销
- **断言**：未注册时零调用、零异常；注册后 `get_fill_listener() is fake` 且 `notify_fill` 触发一次；注销后再次 no-op；注册幂等（重复注册后者生效）
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_listener_port.py -q -k "register or unregister or default_noop"`
- **期望**：退出码 0；用例间无串味（前一用例的监听器不残留）
- **现状**：先红（新模块）

#### TC-PORT-03 旧路径兼容转发：`application/trading/paper_trading_engine.py`  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（兼容性）
- **构造**：从旧模块 import `FillEvent`、`IFillListener`、`register_fill_listener`、`get_fill_listener`
- **步骤**：经旧模块注册 → 经新模块 `notify_fill` 投递
- **断言**：旧模块符号与新模块**同一对象/同一注册位**（注册经旧路径、投递经新路径仍命中）；`FillEvent` 为同一个类
- **命令**：`venv/bin/python -m pytest tests/application/test_fill_listener_port.py -q -k "legacy_forwarder"`
- **期望**：退出码 0；`paper_engine.register_fill_listener is neutralize`（同一函数对象）
- **现状**：先红（转发未落地）

#### TC-PORT-04 依赖方向：trading 不 import watch  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：静态契约（回归）
- **构造**：无
- **步骤**：在 trading 包源码内检索 `qs_watch`
- **断言**：无命中；反向依赖为零
- **命令**：`grep -rn "qs_watch" packages/qs_trading/qs_trading --include='*.py'`
- **期望**：输出为空、退出码 1（grep 无命中）；命中即违约（需回退到端口 + 组合根注册）
- **现状**：基线已绿（守住 RFC 017 §4.2）

### 接缝② 消息投递用例  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-NEWS-01 critical 命中持仓标的 → P1 待办 1 条 + 唤醒 1 次（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向）
- **构造**：持仓 `600519.SH`；消息 `{symbol:'600519.SH', tier:'critical', matched_terms:['减持'], summary:'…'}`；假仓储 + 假唤醒器
- **步骤**：调用消息待办桥（`news_todo_bridge`）→ 读待办与唤醒
- **断言**：`len(todos)==1`；`todos[0].level=='P1'`；`todos[0].action_kind=='rule_change'`；`todos[0].symbol=='600519'`；`evidence['matched_terms']==['减持']` 且 `evidence['summary']` 非空；`wake_calls==1`
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_news_todo.py -q -k "critical_holding_symbol"`
- **期望**：退出码 0
- **现状**：先红（`news_todo_bridge.py` 未落地）

#### TC-NEWS-02 critical 命中持仓板块 → 同款建单（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向）
- **构造**：持仓标的所在板块 `白酒`；消息 `{sector:'白酒', tier:'critical', matched_terms:['限价']}`；`held_sector_map` 映射命中
- **步骤**：调用桥 → 读待办
- **断言**：`len(todos)==1`；`evidence['hit_scope']=='sector'`；`evidence['sector']=='白酒'`；唤醒 1 次
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_news_todo.py -q -k "critical_holding_sector"`
- **期望**：退出码 0
- **现状**：先红

#### TC-NEWS-03 soft 只发卡、不建待办（失败/边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：同 TC-NEWS-01 的持仓，消息 `tier='soft'`
- **步骤**：调用桥
- **断言**：`len(todos)==0`；卡发送被调用 1 次；唤醒 0 次
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_news_todo.py -q -k "soft_only_card"`
- **期望**：退出码 0
- **现状**：先红

#### TC-NEWS-04 重复消息/重复扫描 → 待办数不增（失败/边界·幂等）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（幂等）
- **构造**：同一消息（同 `message_id`）与同一标的连续扫描 3 轮
- **步骤**：第 1 轮建单 → 第 2、3 轮重放
- **断言**：`len(todos)==1`；`wake_calls==1`；卡发送不重复（或按既有去重窗口只发 1 次）
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_news_todo.py -q -k "duplicate_scan_no_new_todo"`
- **期望**：退出码 0
- **现状**：先红

#### TC-NEWS-05 critical 但非持仓（标的/板块都不命中）→ 待办 0（边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：`tier='critical'`，`symbol='000001.SZ'` 不在持仓，板块不在 `held_sector_map`
- **步骤**：调用桥
- **断言**：`len(todos)==0`；卡照发；无唤醒；不产生 `rule_change` 审计
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_news_todo.py -q -k "critical_not_held"`
- **期望**：退出码 0（不猜归属、不建空待办）
- **现状**：先红

#### TC-NEWS-06 交易日 16:30 → 消息扫描执行，日频任务不重复（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向·窗口）
- **构造**：假时钟 `2026-10-21 16:30 +08:00`（交易日）；`_last_meta_scan_date` / `_last_lifecycle_date` / `_last_outcome_backfill_date` 均为当日；消息服务假件记录 `scan` 调用
- **步骤**：调用 `engine._run_sidecar(now)` 两次
- **断言**：`news_scan_calls==2`（每拍都试）；元复核/持仓联动/走势回填/池对账调用次数**不增**（当日已做）；`digest` 不重复；无异常抛出
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_sidecar_window.py -q -k "trading_day_1630_news_runs_daily_once"`
- **期望**：退出码 0；失败时打印各服务调用计数
- **现状**：先红（sidecar 现由 `is_trading_time` 守卫，15:00 后直接 return）

#### TC-NEWS-07 非交易日 / 22:01 → 不扫（边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：假时钟 `2026-10-24 10:00`（周六）与 `2026-10-21 22:01`（交易日但窗外）
- **步骤**：各调用 `_run_sidecar` 一次
- **断言**：`news_scan_calls==0`；其余日频任务同样 0；返回不抛
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_sidecar_window.py -q -k "non_trading_day_no_scan or after_window_no_scan"`
- **期望**：退出码 0
- **现状**：先红

#### TC-NEWS-08 消息源异常 → sidecar 其它段照跑（失败注入）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（失败路径）
- **构造**：消息服务 `scan` 抛 `RuntimeError`
- **步骤**：调用 `_run_sidecar` 一次
- **断言**：异常被吞；同拍其它段（摘要门/日报）调用计数照常；session 被关闭（无泄漏）
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_sidecar_window.py -q -k "news_failure_isolated"`
- **期望**：退出码 0
- **现状**：先红

### 接缝③ 待办闭环用例  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-LOOP-01 不执行 → 规则变更 + 带溯源的审计（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：场景 e2e（正向）
- **构造**：P0 执行待办（`action_kind='trade'`，`trigger_id=501`）+ 规则 `exit_stop`（阈值 9.0）
- **步骤**：`close(terminal='ignored', action_kind='rule_change', next_condition='回踩 9.8 再评估', rule_change={change_kind:'threshold', params:{threshold:8.5}, reason:'跌幅未破位'})`
- **断言**：规则 `threshold==8.5`；`watch_rule_changes` 新增 1 行且 `trigger_id==501`、`change_kind=='threshold'`、`reason` 非空；`todos.terminal=='ignored'`；`next_condition` 已落库
- **命令**：`venv/bin/python -m pytest tests/scenarios/test_watch_exec_loop_e2e.py -q -k "F2_decline_closes_ignored_and_linkage_leaves_audit_trail"`
- **期望**：退出码 0
- **现状**：半绿（引擎侧链路已绿；`TodoService.close` 直调路径未接线 → 见 TC-LOOP-02 的命令组）

#### TC-LOOP-02 关闭接口接线：`close` 成功后调 `RuleChangeLinkage.apply`（缺陷复现）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向接线）
- **构造**：假 `TodoService` 仓储 + 假 `RuleChangeLinkage`（记录 apply 调用）；待办 `trigger_id=501`、`flow_state='L3'`
- **步骤**：`TodoService.close(todo_id, 'ignored', action_kind='rule_change', decision_audit_id='dec-9', next_condition='…', rule_change={...})`
- **断言**：`linkage.apply_calls==1`；入参含 `trigger_id=='501'`、`todo_id`、`change_kind`、`reason`；`apply` 在仓储 close 返回**之后**调用；apply 抛错时 close 回滚（仓储 close 未被提交）
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_todo_close_linkage.py -q -k "close_invokes_linkage_after_persist"`
- **期望**：退出码 0
- **现状**：先红（`todo_service.close` 现无 `RuleChangeLinkage` 引用）

#### TC-LOOP-03 并发关闭 → 后到 409、台账零改动（失败/并发）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（并发）
- **构造**：先成功关闭一次；第二次同 `todo_id` 再关闭（模拟两个请求竞态，后到者读到已终态）
- **步骤**：两次 `close` 调用 → 断言第二次异常类型与台账
- **断言**：第二次抛 `WatchTodoAlreadyClosed`，HTTP 映射 409 `watch_todo_already_closed`；`watch_rule_changes` 计数不增；规则字段不变；`closed_at` 不变
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_todo_close_linkage.py -q -k "concurrent_close_conflict or already_closed_409"`
- **期望**：退出码 0；错误体 `code=='watch_todo_already_closed'`
- **现状**：半绿（服务层已抛，接口级断言与「台账零改动」需新增）

#### TC-LOOP-04 `rule_change` 非法输入 → 400 且零写（失败）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（失败路径）
- **构造**：三组非法请求——`change_kind='乱写'`（白名单外）、缺 `trigger_id` 血缘、`reason` 为空
- **步骤**：逐组调用 close → 读规则、审计、待办
- **断言**：分别返回 400（`watch_todo_invalid_change_kind` / `watch_todo_missing_trigger_trace` / `watch_todo_missing_reason`）；三张表零写入；待办仍 `terminal is None`
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_todo_close_linkage.py -q -k "invalid_change_kind or missing_trigger_trace or missing_reason"`
- **期望**：退出码 0
- **现状**：先红

#### TC-LOOP-05 规则写成功、审计失败 → 同事务回滚（失败注入）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（失败路径·事务）
- **构造**：审计仓储 `record` 抛异常
- **步骤**：close 带合法 `rule_change`
- **断言**：规则字段回滚为原值；`watch_rule_changes` 0 行；待办仍 `terminal is None`；错误码 `watch_rule_change_failed`（500）；不出现「规则改了没审计」
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_todo_close_linkage.py -q -k "audit_failure_rolls_back_rule"`
- **期望**：退出码 0
- **现状**：先红

#### TC-LOOP-06 补挂止盈/减仓规则写 `holding` 并参与下一拍（FR-8 正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向 + 缺陷复现）
- **构造**：持仓 `shares_total=800`；无对应止盈规则
- **步骤**：跑一次持仓联动（补齐规则）→ 读规则 `position_state` → 下一拍求值
- **断言**：新规则 `position_state=='holding'`；下一拍该规则进入取价与求值（`quote_calls` 含该 symbol）；旧规则不被回填
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_position_lifecycle.py -q -k "auto_attach_writes_holding or holding_rule_evaluates_next_tick"`
- **期望**：退出码 0；不写状态时该用例必失败（缺陷复现口径）
- **现状**：先红（`position_lifecycle_service` 无 `position_state` 写入）

#### TC-LOOP-07 缺列 / 未知状态 → fail-open 照常求值（兼容边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（兼容）
- **构造**：规则仓储 `_new_columns_available()` 返回 False（模拟旧库）；另一组 `position_state=None`
- **步骤**：`rule_position_state(rule)` → 引擎分支
- **断言**：读出 `None`；entry 与 exit 均照常求值；`update_fields` 丢弃新字段并 warn，不抛错
- **命令**：`venv/bin/python -m pytest tests/application/test_watch_position_state_branch.py -q -k "unknown_state_fail_open or missing_column"`
- **期望**：退出码 0
- **现状**：基线已绿

### 接缝③ 执行期限用例  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-SLA-01 时区矩阵：带时区 / 裸时间 / 跨日（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（参数化·时区）
- **构造**：参数化三组——`2026-10-21T09:30:00+08:00`、`2026-10-21T01:30:00`（裸时间按 UTC 解释）、`2026-10-20T23:50:00+00:00`（跨日）
- **步骤**：`deadline_at` 计算 → 与 `now` 比较
- **断言**：同一逻辑时刻得到同一比较结果；`aware` 与 `naive` 均先归一到 UTC 再比较；跨日不出现负时延或永不超时
- **命令**：`venv/bin/python -m pytest tests/application/test_sla_job.py -q -k "timezone_matrix"`
- **期望**：退出码 0
- **现状**：先红（执行期限分支不存在；现有 `sla_job` 只在既有 L3 路径做了 UTC 归一）

#### TC-SLA-02 期限前 1 分钟 0 条、期限后 1 分钟 1 条、重复 tick 仍 1 条（正向·幂等）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（正向）
- **构造**：P0 `action_kind='trade'` 未收敛待办，`created_at=now-29min`，`WATCH_EXEC_SLA_MIN=30`
- **步骤**：`now=created_at+29min` 跑一拍 → `+31min` 跑一拍 → 同 `now` 再跑两拍
- **断言**：回执计数依次 `0 → 1 → 1 → 1`；`watch_receipts.kind='timeout'` 计数 1；同一期限周期 digest 相同；`escalate_count` 只 +1
- **命令**：`venv/bin/python -m pytest tests/application/test_sla_job.py -q -k "exec_deadline_before_and_after or exec_timeout_idempotent"`
- **期望**：退出码 0；`deadline_at == created_at + 30min`
- **现状**：先红

#### TC-SLA-03 超时不写 `expired`、待办保持未收敛（边界·语义）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：同 TC-SLA-02，超时已触发
- **步骤**：读待办与触发
- **断言**：`todos.terminal is None`；`todos.closed_at is None`；`triggers.disposition` 仍非终态（`escalated`）；`watch_receipts` 有 timeout 行
- **命令**：`venv/bin/python -m pytest tests/application/test_sla_job.py -q -k "exec_timeout_never_writes_expired"`
- **期望**：退出码 0
- **现状**：先红

#### TC-SLA-04 已收敛待办跳过、不发超时回执（边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：单测（边界）
- **构造**：待办已 `handled`（成交回写已收敛），`due_at` 已过
- **步骤**：跑一拍超时巡检
- **断言**：timeout 回执 0 条；不唤醒；`escalate_count` 不变
- **命令**：`venv/bin/python -m pytest tests/application/test_sla_job.py -q -k "exec_timeout_skips_closed"`
- **期望**：退出码 0
- **现状**：先红

### 接缝③ 统计用例  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-STAT-01 三态计数：executed / declined / timeout（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：接口用例（正向）
- **构造**：样本 3 条 handled(trade)、2 条 ignored、1 条未收敛且超时；治理类（meta_review）1 条
- **步骤**：`GET /api/watch/exec/stats` → 与逐条构造比对
- **断言**：`executed==3`、`declined==2`、`timeout==1`；`total==6`（治理类不计入）
- **命令**：`venv/bin/python -m pytest tests/api/test_watch_exec_stats.py -q -k "three_state_counts"`
- **期望**：退出码 0；响应 200
- **现状**：先红（端点不存在）

#### TC-STAT-02 时延 p50/p95 与台账一致（正向）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：接口用例（正向）
- **构造**：5 条带 `detail.exec.latency_sec` 的样本，取值 `[10, 20, 30, 40, 1000]`
- **步骤**：请求接口 → 用同口径 SQL 计算
- **断言**：`latency_p50_seconds==30`、`latency_p95_seconds==1000`（或按定义的四舍五入口径逐一相等）；`latency_source=='exec_detail'`
- **命令**：`venv/bin/python -m pytest tests/api/test_watch_exec_stats.py -q -k "latency_percentiles"`
- **期望**：退出码 0
- **现状**：先红

#### TC-STAT-03 空数据返回 0 而不是报错（边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：接口用例（边界）
- **构造**：清空样本（空库或空表）
- **步骤**：请求接口
- **断言**：HTTP 200；三个计数均为 0；`p50`/`p95` 为 `null`；不返回 5xx、不返回假 0 时延
- **命令**：`venv/bin/python -m pytest tests/api/test_watch_exec_stats.py -q -k "empty_returns_zeros"`
- **期望**：退出码 0
- **现状**：先红

#### TC-STAT-04 与 `watch_todos` 同口径逐项相等；治理类不进分母（失败/边界）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：接口用例（口径对账）
- **构造**：混合样本（含 `action_kind=None` 的治理待办、`expired` 归档待办、非 `exit_stop` 的 trade 待办）
- **步骤**：请求接口 → 执行同口径 SQL
- **断言**：三个计数与 SQL 逐项相等；`expired` 不计入 `declined`；治理类不在分母；`state_mismatch` 计数可读
- **命令**：`venv/bin/python -m pytest tests/api/test_watch_exec_stats.py -q -k "parity_with_ledger or governance_excluded"`
- **期望**：退出码 0；SQL 口径写进测试注释（分母 = 执行待办，非全部待办）
- **现状**：先红

### 数据迁移用例  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-DB-01 `watch_todos.evidence` 可空列 + 部分索引（正向·幂等）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：迁移用例（quant_test）
- **构造**：迁移前后各读一次 `information_schema`
- **步骤**：执行迁移两次 → 查列与索引 → 写一条带 evidence 的待办 → 再写一条 `terminal` 非空的待办
- **断言**：`evidence` 存在且可空、类型 `jsonb`；部分索引存在，定义为 `(symbol, action_kind) WHERE terminal IS NULL`；重跑无报错（幂等）；索引不覆盖已终态行
- **命令**：`PGDATABASE=quant_test venv/bin/python -m pytest tests/migration/test_watch_todos_evidence_column.py -q`
- **期望**：退出码 0；迁移 `--apply` 重跑第二遍报告 0 变更
- **现状**：先红（`quant.watch_todos` 现无 `evidence` 列，见迁移 `20260918_watch_todo_loop.py`）

### 回归与生产只读核查  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

#### TC-REG-01 watch 包全量回归  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：回归
- **构造**：无
- **步骤**：跑 watch 相关三层（application + scenarios + api）
- **断言**：全绿；无新增 xfail/skip；既有 34 条 `sla_job`、35 条 `fill_sync`、场景矩阵不退化
- **命令**：`venv/bin/python -m pytest tests/application tests/scenarios tests/api -q -k "watch or fill or sla"`
- **期望**：退出码 0
- **现状**：基线已绿

#### TC-REG-02 trading 成交路径回归  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：回归
- **构造**：无
- **步骤**：跑交易账户服务与成交回调相关用例
- **断言**：`execute_trade` 既有响应体与错误码不变；买卖成交落库不变；新增通知不改变返回结构
- **命令**：`venv/bin/python -m pytest tests/application/test_account_trading_service_v2.py tests/application/test_trade_input_type_guard.py -q`
- **期望**：退出码 0
- **现状**：基线已绿

#### TC-REG-03 生产只读核查（成交留痕 / 盘后轮次 / 统计对账）  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **层级 / 类型**：生产只读核查（人工执行，只允许 SELECT）
- **构造**：真实库 `quant_investment`，只读角色
- **步骤**：发布当日与之后连续 5 个交易日，依次执行三条 SQL
- **断言**：① 成交后 `watch_triggers.detail` 含 `exec` 的行数 > 0，且 `exec.latency_sec` 非负；② 交易日 15:00 后日志存在消息扫描轮次，且 `watch_receipts` 无重复 timeout；③ `/api/watch/exec/stats` 三态计数与该库同口径 SQL 逐项相等
- **命令**：
  - `psql "$PGDSN" -c "select count(*) from quant.watch_triggers where detail ? 'exec'"`
  - `psql "$PGDSN" -c "select count(*) from quant.watch_todos where level='P0' and action_kind='trade' and terminal is null"`
  - `psql "$PGDSN" -c "select terminal, count(*) from quant.watch_todos where action_kind='trade' group by terminal"`
- **期望**：①>0；②与接口计数逐项相等；0 条重复 timeout（同一 `(todo_id, deadline_at)` 只有一条）
- **现状**：先红（生产当前 `exec` 明细 0 行，P0 待办 #107 悬空）

## 架构与依赖  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **被测切片**：`qs_trading` 的成交写点与端口 → `qs_watch` 的 `FillSyncService` / `news_todo_bridge` / `TodoService.close` + `RuleChangeLinkage` / `sla_job` / `engine._run_sidecar` / `/api/watch/exec/stats`。测试只 import 生产模块，不复制业务逻辑。
- **替身边界**（端口假件）：`IWatchTodoRepository`、`IWatchTriggerRepository`、`IWatchRuleRepository`、`IReceiptRepository`、通知器、唤醒器、持仓读取、`IFillListener`、消息源与 `held_sector_map`。替身只替代**出口与取数**，判定与编排全部走生产代码。
- **依赖方向**：测试的装配方向与生产一致——组合根（`watch_bootstrap`）注册监听器；`qs_trading` 不得 import `qs_watch`（TC-PORT-04 用 grep 静态守门）。场景 e2e 通过 `register_fill_listener(FillSyncService(...))` 完成接线，而不是 monkeypatch 内部函数，避免测到「假接线」。
- **外部依赖与降级**：单测与 e2e 零外部依赖（无网络、无券商、无飞书）；迁移与统计对账类用例依赖本地 `quant_test`（`pytest` 启动时由 coroutine/conftest 三层守卫强制 `_test` 后缀，误连生产会在启动期失败）；生产只读核查只读，不可写。
- **与既有测试架构的差异**：既有 `fill_sync` / `sla_job` 用例把假件写在各自文件内；本期新增用例**复用**既有假件（`tests.application.test_sla_job` 的 FakeTodo/FakeTodoRepo/FakeReceiptRepo、`tests.services.test_watch_engine` 的 `make_rule`/`FakeQuoteService`/`FakeNotifier`），不新建假件框架。唯一新增基础设施是 `autouse` 的监听器注销 fixture（防串味）。

## 数据模型  serves: FR-1, FR-2, FR-7

本节描述**测试事实模型**：用例构造哪些种子行、断言哪些字段；不是业务模型的复述。

- **实体与字段（种子事实与判据）**：

| 表 / 端点 | 用例写入 / 构造的关键字段 | 用例断言点 |
|---|---|---|
| `quant.watch_rules` | `symbol`、`linked_account`、`intent`、`level`、`enabled`、`lifecycle_stage`、`position_state` | `position_state ∈ {holding, none}`；exit 族 `enabled=false`；entry 族仍在册 |
| `quant.watch_todos` | `rule_id`、`trigger_id`、`symbol`、`level`、`action_kind`、`flow_state`、`terminal`、`close_reason`、`next_condition`、`decision_audit_id`、`evidence` | `terminal ∈ {handled, ignored} or None`；`action_kind`；`evidence` 子键；`closed_at` 与 `terminal` 成对 |
| `quant.watch_triggers` | `rule_id`、`disposition`、`detail` | `disposition`；`detail.exec.{trade_id,price,latency_sec,source}` |
| `quant.watch_rule_changes` | `rule_id`、`change_kind`、`reason`、`trigger_id`、`todo_id` | 行数；`trigger_id` 非空；`change_kind` 在白名单内 |
| `quant.watch_receipts` | `todo_id`、`kind`、`digest`、`due_at` | `kind='timeout'` 计数；同期限 digest 相同 → 幂等 |
| `quant.simulation_positions` | `account_name`、`symbol`、`shares_total`、`shares_available` | `shares_total` 决定 holding/none 与是否收敛 |
| `GET /api/watch/exec/stats` | 无写入 | `executed`/`declined`/`timeout`/`latency_p50_seconds`/`latency_p95_seconds`/`latency_source` |

- **约束与不变量**（用例必须守住的既有契约）：
  1. 不新增 `terminal` / `disposition` 枚举：超时是**状态**，不是终态，绝不写 `expired`；
  2. `terminal` 与 `closed_at` 成对（DB CHECK）；
  3. `action_kind ∈ {trade, rule_change}` 的已终态待办必须有 `decision_audit_id`；
  4. `ignored` 必须有 `next_condition`；
  5. `position_state` 只有 `holding`/`none` 可确认，`None` 一律 fail-open 求值。
- **迁移与回填**：本期唯一的 schema 变更是 `quant.watch_todos` 新增可空列 `evidence jsonb` + 部分索引 `(symbol, action_kind) WHERE terminal IS NULL`；**无回填**（历史待办 evidence 保持 NULL）；迁移可重复执行、失败不留半成品；其余表不动。回滚 = 保留列不读（列存在无害），缺列环境按旧行为 fail-open。
- **生命周期**：测试种子只落 `quant_test`，每用例用事务回滚或显式清理（`DELETE` 按 `created_at` + 测试标记）；生产只读核查不做任何写入，核查 SQL 只允许 `select`。

## 接口设计  serves: FR-1, FR-3, FR-5, FR-6, FR-7

本节把「被测契约」写成可评审的接口：每一个都对应上面的用例组。

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `qs_trading/application/ports/fill_listener.py`（`FillEvent` / `IFillListener` / `register_fill_listener` / `get_fill_listener` / `unregister_fill_listener` / `notify_fill`） | `FillEvent(account_name, symbol, action, shares, price, trade_id, order_id, decision_audit_id, filled_at, source)`；注册对象须实现 `on_fill(event)` | `notify_fill` 返回 None，副作用 = 调一次监听器；`get_fill_listener()` 返回当前监听器或 `None` | 注册非协议对象 → `TypeError`（装配期）；监听器抛错被吞 + 日志 + 计数，不向成交路径冒泡 | 旧路径 `application/trading/paper_trading_engine.py` 保留同名符号并转发；`FillEvent` 新字段只允许带默认值 |
| IF-2 | `notify_fill` 成交后通知（`AccountTradingService.execute_trade` 调用点） | 已落库的 trade 事实（含 `trade_id`、成交价、股数、`account_name`、`decision_audit_id` 或 `None`） | 成交响应不变；副作用 = 成交 commit 后调用 `notify_fill` | 通知异常 → 记日志 `fill_notify_error`，成交仍成功；无新增 HTTP 错误码 | 响应体与错误码不变；挂单撮合走同一路径自动覆盖 |
| IF-5 | `qs_watch/application/services/watch_engine/news_todo_bridge.py` | 消息命中结果 `{message_id, symbol?, sector?, tier, matched_terms, summary}` + 持仓/板块映射 | `critical` 且命中 → P1 待办 1 条（`action_kind='rule_change'`、`evidence` 记摘要与命中词）+ 唤醒 1 次；`soft` → 仅发卡 | 建单失败 → 记日志不阻断发卡；唤醒失败 → 折进 1 张卡；无法判归属 → 跳过并计数，不猜 | 新模块，无旧调用方；`evidence` 可空列 additive，缺列/旧库不写 evidence、建单行为不变 |
| IF-3 | `POST /api/watch/todos/{id}/close` 的 additive `rule_change` | 既有 `terminal/close_reason/next_condition/action_kind/decision_audit_id` + 可选 `rule_change: {change_kind, params, reason}` | 关闭后的待办 + `watch_rule_changes` 1 行（`trigger_id` 必填） | 已终态 → 409 `watch_todo_already_closed`；`change_kind` 越白名单 → 400 `watch_todo_invalid_change_kind`；缺 `trigger_id` 血缘 → 400 `watch_todo_missing_trigger_trace`；审计写失败 → 500 `watch_rule_change_failed` 且整体回滚 | additive：不传 `rule_change` 时行为与今天完全一致；不新增枚举值 |
| IF-4 | `GET /api/watch/exec/stats` | 无 | `{executed, declined, timeout, total, latency_p50_seconds, latency_p95_seconds, latency_source, state_mismatch}` | 空数据 → 200 全 0；DB 异常 → 503 `watch_exec_stats_unavailable`（不返回假 0） | 新端点 additive；不改 `GET /api/watch/outcomes/stats` 的命中率口径 |
| IF-6 | `WatchEngine._run_sidecar` 的盘中段 / 盘后段划分（含 `quant.watch_todos.evidence`） | 当前时刻（aware 或 naive，统一归一到 UTC 后判窗） | 交易日 08:00–22:00 内消息扫描可被调用；其余日频任务维持当日一次；非交易日全部不跑 | 段内异常只记日志，不阻断同拍后续段；窗外返回 `{'scanned': False, 'reason': …}` 不抛 | 消息服务内部窗口不变；不引入第二套时钟；`evidence` 列缺列时 fail-open |

#### IF-1 成交回调端口（trading 侧中立端口）  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

trading 侧唯一的成交事实出口。发布者只有一个：`AccountTradingService.execute_trade` 在成交**落库之后**调用 `notify_fill(event)`；订阅者只有一个：`qs_watch` 的 `FillSyncService`，由组合根注册。注册位是模块级单槽（不是 pub/sub），因此没有投递顺序与丢失语义；未注册时 `notify_fill` 是 no-op，生产行为与今天完全一致。端口不产生订单、不读数据库、不做幂等，幂等由消费方按 `trade_id` 保证。

**错误码**

- 注册非协议对象 → `TypeError`（只可能出现在装配期，宿主启动即暴露，不进热路径）。
- `on_fill` 抛错 → 被 `notify_fill` 吞掉并记 `fill_notify_failed`，同时 `fill_notify_error_total` 计数 +1；**不向成交路径冒泡**，`execute_trade` 视为成功。
- 无监听器 → 返回 None，不报错、不打日志噪音。

**兼容性**

`application/trading/paper_trading_engine.py` 保留 `FillEvent` / `IFillListener` / `register_fill_listener` / `get_fill_listener` 同名符号并转发到新模块（旧 import 与旧测试不破坏），二者共享同一注册位（TC-PORT-03 断言同一函数对象）。`FillEvent` 新增字段必须带默认值；`source` 已有默认值，消费侧不得据此改变收敛行为。

#### IF-2 `execute_trade` 成交后通知点  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

`execute_trade` 在 trade 行 commit 成功后、返回结果前调用一次 `notify_fill`，事件字段取自刚落库的事实：`account_name`、`symbol`、`action`、`shares`、`price`、`trade_id`、`order_id`、`decision_audit_id`（取 `_auto_record_decision` 返回值；拿不到时为 `None`，消费侧降级为 `trade:<trade_id>` 并标 `audit_degraded`，**不虚报审计**）、`filled_at`。挂单撮合（`execute_pending_orders`）复用同一路径，因此自动覆盖。

**错误码**

- 通知异常 → 吞掉 + `fill_notify_error` 日志；成交响应保持成功（HTTP 2xx 与返回体不变）。
- 不新增 HTTP 错误码：通知不属于成交前置校验，任何通知失败都不得把一笔已落库的成交改成失败。
- 事件构造失败（如 trade 缺 id）→ 跳过本次通知并记 warn，不阻塞成交。

**兼容性**

响应体字段不增不减；若未来要暴露「回执已发」只能加可选字段。`submitted_by`、`signal_id`、`strategy_name` 等既有入参语义不变。对调用方而言这是**零行为变更**的旁路（与既有 `_auto_record_decision` 的纪律同源）。

#### IF-5 消息待办桥（critical → P1 + 唤醒）  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

消费消息扫描结果：`tier='critical'` 且命中持仓标的或持仓板块 → 建 1 条 P1 待办（`action_kind='rule_change'`，`evidence` 存 `message_id`、`summary`、`matched_terms`、`hit_scope`（`symbol`/`sector`））并按既有 owner 路由唤醒 agent；`tier='soft'` 维持发卡、不建单、不唤醒。同一 `(symbol, action_kind)` 在未收敛窗口内不重复建单（复用待办仓储的未收敛查询）。桥不判断「消息是否破坏逻辑」——判断永远在 agent（D-3 边界）。

**错误码**

- 建单失败 → 记日志、继续发卡（消息不能因建单失败而静默消失）。
- 唤醒失败 → 折进 1 张卡（沿用既有「多失败合成一张卡」口径），不重复催。
- 入参既无 `symbol` 也无 `sector`，或板块解析不出 → 跳过并计数 `skipped_no_owner`，**不猜归属**。
- 去重命中 → 不建单、不唤醒，返回 `{'deduped': True}`。

**兼容性**

新模块 additive；`quant.watch_todos.evidence` 可空，旧库缺列时跳过 evidence 写入、建单行为不变。既有 `news_alert` 卡路径不变（soft 与 critical 都照旧发卡），桥只增加「建单 + 唤醒」这一层副作用，可单独关掉（装配时不注入桥即回退旧行为）。

#### IF-3 close 接口的 `rule_change` 动作  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

agent 选择「不执行」时，关闭待办的请求体新增可选 `rule_change`：`change_kind`（白名单：`threshold`/`cooldown`/`retire`/`suppress` 及其既有 repair 动作）、`params`（对应动作的参数）、`reason`（必填）。`TodoService.close` 校验通过并成功落库后，在同一事务内调用 `RuleChangeLinkage.apply(trigger_id, todo_id, change_kind, params, reason)`：改规则字段 + 写 `watch_rule_changes`（`trigger_id` 必填，来自待办/触发血缘）。`terminal` 仍只允许 `handled|ignored|expired`，`ignored` 仍必须带 `next_condition`。

**错误码**

- 已终态再次关闭 → 409 `watch_todo_already_closed`（台账零改动，领域先抛）。
- `change_kind` 不在白名单 → 400 `watch_todo_invalid_change_kind`。
- 缺 `trigger_id` 血缘或 `reason` 为空 → 400 `watch_todo_missing_trigger_trace` / `watch_todo_missing_reason`。
- 规则更新或审计写入失败 → 500 `watch_rule_change_failed`，**整体回滚**（不允许「规则改了但没审计」）。
- 不传 `rule_change` → 走原有关闭路径，零新错误码。

**兼容性**

纯 additive：旧调用方不传新字段照旧；不新增 `terminal`/`disposition` 枚举；`change_kind` 复用既有白名单，不为「状态纠偏」发明新值。响应体只新增可选的变更摘要字段（如 `rule_change_applied`），默认不带。

#### IF-4 执行闭环统计端点  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

返回执行闭环三态计数与处理时延分位。分母口径固定为**执行待办**：`watch_todos.action_kind='trade'` 且其规则 `intent` 属退出止损族；治理类（`meta_review` 等）与 `expired` 归档不计入 `declined`。时延取 `watch_triggers.detail.exec.latency_sec`（缺失时按 `todos.created_at → closed_at` 估算并在 `latency_source` 标明来源）。`timeout` 取未收敛且已过执行期限的待办数（不写终态）。该端点**不**替代 `GET /api/watch/outcomes/stats`（那是触发后 5/10/20 交易日预判命中率）。

**错误码**

- 空数据 → HTTP 200，计数全 0，分位为 `null`（不报错、不返回 5xx）。
- 库不可用 → 503 `watch_exec_stats_unavailable`（明确失败优于返回假 0）。
- 参数非法（若未来加分页/窗口）→ 400 `watch_exec_stats_invalid_param`。

**兼容性**

新端点 additive，无旧调用方；响应字段只增不改；分母口径写进响应（如 `scope='exec_todos'`）以便对账。查询必须是单条聚合 SQL，禁止「先取 200 行再过滤」（既有触发统计的截断缺陷不得复制）。

#### IF-6 sidecar 盘中/盘后分段  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

`_run_sidecar` 拆成盘中段与盘后段：交易日 08:00–22:00 内**消息扫描每拍可尝试**（服务内部仍有 15 分钟节流，因此 16:30 能扫到盘后公告），其余日频任务（摘要门、元触发复核、持仓生命周期联动、持仓板块映射重建、走势回填、池级对账、收盘日报）维持「当日一次」的既有节奏；非交易日全部不跑。判窗只用一套时钟（交易日 + 时间窗），不新增第二套判定。

**错误码**

- 段内异常 → 只记日志，不阻断同拍后续段，不改变 sidecar 线程存活。
- 窗外 → 返回 `{'scanned': False, 'reason': '非扫描窗口（交易日 08:00–22:00）'}`，不抛错。
- 服务未装配 → 跳过该段（与今天一致，不报错）。

**兼容性**

消息服务内部的 08:00–22:00 窗口不变，改动只是「让它有机会被调用」；其余任务节奏一秒不变。回退方式 = 恢复到旧守卫（交易时段才跑），无需数据迁移。`quant.watch_todos.evidence` 的列变更与分段互不影响：缺列时桥跳过 evidence、扫描照跑。

## 备选方案  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 端口假件单测 + `tests/scenarios/` 场景 e2e + 生产只读核查三层，用例写到可执行命令 | 语义层可穷举边界、e2e 证明真实接线、只读核查证明生产口径；零外部依赖、秒级反馈 | 需要维护假件与真实仓储签名一致（用端口稳定性用例守）；e2e 只到组合根，不含真实 DB 约束 | — |
| B | 全部用真库 e2e（`quant_test` 起库跑全链路） | 能覆盖 DB CHECK、事务回滚与索引行为 | 每条用例要建库/清库，反馈从秒级退化到分钟级；并发关闭与超时矩阵难以确定性构造 | 覆盖率提升有限，却把 CI 时长与 flaky 风险放大；DB 相关断言已收敛到 TC-DB-01 与 TC-STAT 对账 |
| C | 只加单元测试，不写场景 e2e | 最便宜，改动后立刻有回归网 | 测不到「组合根有没有注册监听器」「close 有没有调 linkage」这类接线缺陷——恰恰是本期的三类缺陷 | 本期的历史缺陷全部是**接线缺失**（端口唯一填报点在 paper 引擎、`RuleChangeLinkage` 零调用），只测单测等于不测 |
| D | 直接在生产上验证（只读 SQL + 日志） | 零测试代码，证据最真实 | 只能事后发现，资损类缺陷一次就够；无法构造部分成交、重复事件、时区跨日等边界 | 生产核查保留为第三层（TC-REG-03），但不能替代可重复的前置证据 |
| E | 什么都不做 | 零成本 | 三条接缝继续无回归网，`RuleChangeLinkage` 类死线随重构漂移，超时 +8h 已复发的缺陷必然再发 | 本期修复本身就会改动成交写点与关闭接口，没有回归网等于裸奔上线 |

## 四风险与证据  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 这些用例真能拦住资损类回归吗 | 生产 `watch_triggers.detail` 含执行明细 0 行、P0 待办 #107 悬空；FR-1 的失败结果（部分成交被当成已收敛）正是本轮要防的口径事故；e2e F1 已能逐字段证伪 | 部分：正向与边界可证伪，生产样本量为 0，需 TC-REG-03 累积 5 个交易日 |
| 可用性 | 用例维护成本高吗、假件会不会漂移 | 既有 35 条 `fill_sync` 与 34 条 `sla_job` 用例复用同一批假件（`FakeTodo`/`FakeTodoRepo`/`FakeReceiptRepo`、`make_rule`/`FakeQuoteService`/`FakeNotifier`）；`test_port_method_set_is_stable` 已用签名断言防假件漂移 | 部分：假件有稳定性守卫，但新增 6 个文件的清理与注销纪律要进评审 |
| 可行性 | 端口假件与场景 e2e 能覆盖三条接缝吗 | 场景矩阵 `tests/scenarios/test_watch_exec_loop_e2e.py` 已跑通 F1/F2/F3 三态与 G1/G2 两门；paper 侧回调异常不影响落库已被 35 条用例证明（`:726-790`）；组合根注册测试已存在（`test_fill_sync_factory_wiring.py`） | 已验证（技术路径已被既有实现与用例证明） |
| 商业可行性 | 成本能接受吗（CI 时长、维护人力、上线风险） | 单测与 e2e 均为进程内假件，无外部网络与 DB；生产核查为 3 条 SELECT、人工 5 分钟；不新增依赖、不新增服务 | 已验证（成本以 CI 分钟与人工核查计，量级可忽略） |

**未验证项的补课计划**：价值风险（生产样本 0）→ 用 TC-REG-03 在发布当日与之后 5 个交易日累计 `detail.exec` 行数，达 0 行即判定「回写未生效」并回滚；可用性风险（假件漂移）→ 端口稳定性用例先跑，签名不一致即红；由 agent 在 M2 出口前给出结论。

## 失败模式与回滚  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 假件与真实端口漂移 | 仓储签名或返回结构变更，假件未同步 | 用例假绿，回归网失效 | `test_port_method_set_is_stable` / 端口签名对比 | 以端口定义为准修假件；签名用例先红后放行 | agent（测试负责人） |
| 时区依赖机器环境 | `TZ` 不同（UTC vs Asia/Shanghai），裸时间被判成不同时刻 | 超时用例本机绿、CI 红（或反过来） | TC-SLA-01 时区矩阵；同一用例 `TZ=UTC` 与 `TZ=Asia/Shanghai` 双跑 | 用例内一律显式 `tzinfo`；比较前归一到 UTC | agent |
| 监听器串味（用例间残留） | 前一用例注册监听器未注销 | 后续用例多收敛一次或误报 | `autouse` 注销 fixture + 用例内断言 `get_fill_listener() is None` | 补注销；串味用例立即红 | agent |
| 误连生产库 | 测试进程连到 `quant_investment` | 测试写生产台账（最坏情况） | conftest 三层守卫（库名必须 `_test`）；启动期即失败 | 立即停跑；按备份恢复被写行；禁止在测试里用生产 DSN | 运维 + 投资人 |
| 先红用例长期不转绿 | 缺陷未修但用例已合入，被当成「已知失败」忽略 | 闭环语义悄悄缺失，验收失真 | 先红清单与 FR 绑定；里程碑出口 = 红转绿 | 到期未转绿即判里程碑不通过；不得以 xfail 替代 | 投资人 |
| 生产只读核查误写 | 核查 SQL 被写成 `update`/`delete` 或用了可写角色 | 生产台账被改 | 只提供 `select` 语句；用只读角色；核查前人工复核语句 | 立即停止；按审计日志恢复；核查不留痕外的东西 | 运维 |
| 统计口径漂移 | 分母从「执行待办」悄悄扩成「全部待办」 | 三态计数虚高，验收结论错 | TC-STAT-04 用同口径 SQL 逐项对账 | 回退口径，补一条口径断言 | agent |

- **开关**：无新增运行时开关。测试侧只靠「装配时是否注入桥/监听器」控制副作用——不注入即旧行为，这是本期的唯一降级面。生产回滚 = 从组合根移除 `register_fill_listener(FillSyncService(...))` 与消息桥装配，重启即回到今天的行为。
- **回滚演练**：M3 出口前演练一次「注销监听器 → 跑 e2e 断言回落旧行为」（预期 5 分钟内完成，无数据迁移）；生产侧回滚由 `launchctl kickstart -k gui/501/com.pi-investment.v2-api` 重启生效，实测约 20 秒恢复。
- **不可逆动作**：生产台账行不可逆（无软删除）。事前保护：测试只连 `quant_test`；生产核查只读；`watch_rule_changes` 与规则更新同事务，失败整体回滚。

## 跨关注点  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 不适用新增攻击面 | 测试不连券商、不下单、不持有凭证；生产核查用只读角色并只跑 `select`；用例参数不含真实账号密钥 |
| 隐私与合规 | 不采集个人信息 | 种子数据为虚构标的与账户名（`agent`/`test-*`）；消息摘要用固定样例文本，不含真实持仓人信息 |
| 成本 | 可忽略 | 单测与 e2e 进程内运行、无外部调用；新增 6 个测试文件，CI 增量约 10–20 秒；生产核查 3 条 SELECT |
| 可观测性 | 失败可定位到字段 | 每条用例断言固定字段（terminal / disposition / position_state / trigger_id / 计数）；失败时打印首个不等字段；生产侧对账 SQL 与接口口径同源 |
| 性能与容量 | 不构成压力 | 无新增热路径查询：`/exec/stats` 单条聚合 SQL；`evidence` 部分索引只服务未收敛行；e2e 单条 <1s |
| 文档与支持 | 需两份说明书 | 本文提供命令与期望值；值班手册补「先红清单怎么读、生产核查三条 SQL、回滚开关在哪」，由 agent 在 M3 前提交给运维 |

## 交付拆分与里程碑  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 契约冻结 | 端口用例组 + 成交通知点用例组 + 既有回归组跑通 | TC-PORT-01～04、TC-FILL-06、TC-REG-02 全绿；端口符号与签字确认一致 | agent（测试） | 2026-10-22 |
| M2 三接缝矩阵 | 消息投递、待办联动、执行期限三组用例落地并红转绿 | TC-NEWS-01～08、TC-LOOP-01～07、TC-SLA-01～04 全绿；先红清单清零 | agent（测试） | 2026-10-23 |
| M3 统计与生产核查 | 统计端点用例 + 迁移用例 + 生产只读核查跑满 5 个交易日 | TC-STAT-01～04、TC-DB-01 全绿；TC-REG-03 三条 SQL 连续 5 个交易日无偏差；回滚演练完成 | agent（测试）+ 运维 | 2026-10-30 |

## 需求追溯  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **指标定义**：M-1 成交回写率 = 含 `detail.exec` 的已收敛执行待办 / 全部已收敛执行待办（目标 100%）；M-2 状态时延 = 买入成交 → `position_state='holding'` 的 p95（目标 ≤ 1 拍）；M-3 消息投递比 = critical 命中持仓的建单数 / 命中数（目标 1:1，重复建单 0）；M-4 期限准确率 = 期限内误发 0、重复发 0；M-5 统计一致率 = 接口与台账同口径逐项相等（目标 100%）；M-6 红转绿率 = 先红用例转绿数 / 先红总数（目标 100%）。

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | 方案总览·接缝① / 接口设计 IF-1、IF-2 | TC-FILL-01、TC-FILL-03、TC-FILL-04、TC-FILL-05、TC-FILL-06、TC-FILL-08、TC-PORT-01～03 | M-1 |
| FR-2 | 方案总览·接缝① / 数据模型 | TC-FILL-02、TC-FILL-07、TC-LOOP-07 | M-2 |
| FR-3 | 方案总览·接缝② / 接口设计 IF-5 | TC-NEWS-01、TC-NEWS-02、TC-NEWS-03、TC-NEWS-04、TC-NEWS-05 | M-3 |
| FR-4 | 方案总览·接缝② / 接口设计 IF-6 | TC-NEWS-06、TC-NEWS-07、TC-NEWS-08 | M-3 |
| FR-5 | 方案总览·接缝③ / 接口设计 IF-3 | TC-LOOP-01、TC-LOOP-02、TC-LOOP-03、TC-LOOP-04、TC-LOOP-05 | M-6 |
| FR-6 | 方案总览·接缝③ / 接口设计 IF-6 | TC-SLA-01、TC-SLA-02、TC-SLA-03、TC-SLA-04 | M-4 |
| FR-7 | 方案总览·接缝③ / 接口设计 IF-4 | TC-STAT-01、TC-STAT-02、TC-STAT-03、TC-STAT-04、TC-DB-01 | M-5 |
| FR-8 | 方案总览·接缝③ / 数据模型 | TC-LOOP-06、TC-LOOP-07 | M-6 |

- **反向核对**：39 条用例全部至少映射一条 FR；无「有用例但无需求」的孤儿用例。M-6 覆盖 25 条先红用例，是三个里程碑的共同出口条件。

## 常见问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 回答 |
|---|---|
| 为什么不直接 monkeypatch 成交写点，而要新增中立端口？ | monkeypatch 测的是「测试自己塞进去的假接线」，测不到组合根有没有注册；且让 trading 反向 import watch 会违反 RFC 017 §4.2 的单向依赖。端口是唯一能让「谁注册、注册到哪」被断言的结构。 |
| 为什么场景 e2e 不用真库？判据不是都在库里吗？ | 判据是「台账字段被写成什么」，假仓储同样能给出字段级事实，且能把部分成交、重复事件、并发关闭构造成确定性输入。真库约束（CHECK、索引、事务）单独由 TC-DB-01 与 TC-STAT-04 覆盖，两类证据不互相替代。 |
| 25 条先红用例会不会把 CI 打红、挡合并？ | 会，所以先红按里程碑分组放行：M1 只要求端口与通知点两组转绿；未转绿组用 `-k` 排除，但排除清单写在里程碑出口里，到期未转绿即判不通过——不允许用 xfail 长期挂着。 |
| 超时用例怎么摆脱机器时区？ | 用例内一律显式带 `tzinfo`，比较前归一到 UTC；TC-SLA-01 同时覆盖「裸时间按 UTC 解释」与「跨日」。CI 用 `TZ=UTC` 与 `TZ=Asia/Shanghai` 各跑一遍，结果必须一致。 |
| 生产只读核查谁做、多久做一次？ | 运维执行、agent 出结论，发布当日 + 之后连续 5 个交易日；三条 SQL 固定，只允许 `select`。任一条不达标即回到「回写未生效」的判定，按回滚开关退。 |
| 统计与台账不一致时先查什么？ | 先查分母（是否误把治理类/`expired` 算进 `declined`），再查时区（`created_at` 与 `closed_at` 是否同一基准），最后查时延来源（`latency_source` 是 `exec_detail` 还是回退估算）。三个都在用例里有对应断言。 |
| 消息待办会不会淹没 agent 的队列？ | 只有 `critical` 且命中持仓标的或板块才建单，且同一 `(symbol, action_kind)` 未收敛窗口内不重复；TC-NEWS-03/04/05 直接钉住「soft 不建」「重复不增」「非持仓不建」。 |
| 6 个月后这套用例会成为负担吗？ | 负担点只有假件漂移与先红清单；两者都有守卫（端口签名用例 + 里程碑出口）。真正会腐化的是生产核查 SQL 的口径，所以它写死了分母并在 TC-STAT-04 与接口同源对账。 |

## 开放问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 先红用例是否进 CI 门禁 | 全量红即挡合并 / 按里程碑分组放行 | 投资人 | 2026-10-22 |
| 生产只读核查频率 | 发布当日一次 / 发布当日 + 连续 5 个交易日 | 运维 | 2026-10-23 |
| p95 的最小样本量 | 全量样本直接算 / 少于 20 条时返回 `null` 并标 `sample_insufficient` | agent | 2026-10-22 |
| 消息待办去重窗口口径 | 同标的 1 小时 / 同 `message_id` 永久去重 | agent | 2026-10-22 |
| 「状态滞后」是否计入 `state_mismatch` 的验收阈值 | 计入但只告警 / 计入且设阈值 | 投资人 | 2026-10-23 |

## 附录  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **相关文档**：`docs/requirements/REQ-261021194640-69b8/requirement.md`（8 条 FR 与判据）；`docs/rfcs/017-watch-execution-loop-position-state-per-rule-interval.md`（三态闭环语义、成交回执与超时口径）；`.dsh/file-format-specs/design/spec.yaml`（本文格式门禁）；`packages/qs_watch/CLAUDE.md`（包边界与常见任务路径）。
- **既有用例基线**：`tests/application/test_fill_sync_service.py`（35 条）、`tests/application/test_fill_sync_factory_wiring.py`、`tests/application/test_watch_position_state_branch.py`、`tests/application/test_sla_job.py`（34 条）、`tests/application/test_rule_change_linkage.py`（39 条）、`tests/application/test_watch_position_lifecycle.py`、`tests/scenarios/test_watch_exec_loop_e2e.py`（9 条）；本期新增 `tests/application/test_fill_listener_port.py`、`tests/application/test_account_trading_fill_notify.py`、`tests/application/test_watch_news_todo.py`、`tests/application/test_watch_sidecar_window.py`、`tests/application/test_watch_todo_close_linkage.py`、`tests/api/test_watch_exec_stats.py`、`tests/migration/test_watch_todos_evidence_column.py`、`tests/scenarios/test_watch_news_todo_e2e.py`。
- **命令约定**：全部命令在仓库根 `quantsys-v2/` 执行，解释器 `venv/bin/python`；迁移与统计对账类用例需 `PGDATABASE=quant_test`。生产核查只读、由人执行。
- **评审记录**：待评审（2026-10-21 提交）；未闭环项见「开放问题」。
- **变更历史**：2026-10-21 初稿：三层测试策略、39 条用例（25 条先红）、8 条 FR 全量追溯。
