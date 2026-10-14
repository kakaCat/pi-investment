# 拆分计划（REQ-261007101318-c392）

**目标**：把「盯盘通知四处契约」（休市日闸门 / 名称兜底 / 外发审计+来源 / 意图·级别·闭环解耦）落成可验收的台账，
并补齐设计文档登记的**未覆盖用例**，最后用真实交易日（2026-10-08 复市）回执结单。

**做法**：本需求的代码在需求/设计阶段已按用户「你直接改」的指令先行落地并验证
（228 条定向 + 621 条 key 扫描全过；审计表两库已建；服务 12:50 重启生效）。
故本计划是**回填式计划**：t1~t4 把已落地的四条 FR 登记成卡并绑定证据（执行 = 复核 + 存证，不做新开发），
t5 补掉设计文档 §6 登记的未覆盖用例，t6 出真实交易日回执并汇总验收材料。

**与既有计划的关系**：不新建子系统、不改数据模型之外的结构；`watch_triggers` 等既有台账一律不动。

## 任务表（计划 key 为 tasks[] 的键，逐行覆盖）

| 计划 key | 标题 | 阶段 | 端侧 | 依赖 | 验收（可跑） | 工作量 |
|---|---|---|---|---|---|---|
| t1 | FR-1 休市日闸门：`tick()` 日级收敛到 `TradingDayGuard`（回填） | implement | backend | — | `pytest tests/services/test_watch_engine_trading_day_gate.py -q` → 4 passed；且断言「休市日 `tick()==[]` **且** `repo.calls==0`」 | S（1 文件 + 1 测试文件，改动 ~60 行） |
| t2 | FR-2 名称兜底：禁止把代码当名称（回填） | implement | backend | — | `pytest tests/notification/test_req_c392_notification_contract.py -q -k name` → passed；且 `name` 解析失败时传给 facade 的值为 `None`（非 symbol） | S（2 生产文件 + 1 测试文件） |
| t3 | FR-3 外发审计 + 来源标识（回填，含建表迁移） | implement | backend | — | 两库 `SELECT count(*) FROM quant.notification_audit` 可取；`pytest tests/notification/test_notification_audit_repository.py -q` → 4 passed；SQL 能查回 `sender_id` | M（新建 2 + 修改 3 + 迁移 1） |
| t4 | FR-4 文案契约：意图/处置级别 + 闭环承诺解耦（回填） | implement | backend | t2 | `pytest tests/notification/test_req_c392_notification_contract.py tests/application/test_watch_t12_wiring.py tests/application/test_watch_t12_todo_creation.py -q` → 全 passed；断言 `closed_loop=False` 时无「处置入口」而仍有意图/级别 | M（5 修改文件，含 3 处旧契约翻新） |
| t5 | 补齐设计登记的未覆盖用例（`run_forever` 整环 / 跳过留痕去重 / 装配失败降级） | test | backend | t1, t3 | 新增/扩展用例后 `pytest tests/services/test_watch_engine_trading_day_gate.py tests/notification -q` → 全 passed，且总量 ≥ 基线（228） | M（3 个用例 + 1 个可能的新测试文件） |
| t6 | 真实交易日回执 + 验收材料（时间型） | test | backend | t5 | 2026-10-08 盘后：`select ... from quant.notification_audit where occurred_at::date='2026-10-08'` 有 `watch_triggered` 行且 `sender_id` 非空；`quant.watch_triggers` 当日有触发记录且卡片含名称 | S（跑查 + 写 verification.md） |

## 覆盖对照（人读汇总；门禁只认**卡上的** `requirement_refs`）

| 功能点 | 承接卡 |
|---|---|
| FR-1 休市日闸门 | t1（主）、t5（补用例）、t6（回执） |
| FR-2 名称兜底 | t2（主）、t4（契约同测）、t6 |
| FR-3 外发审计 + 来源 | t3（主，含迁移）、t5（补降级用例）、t6 |
| FR-4 意图/级别 + 闭环解耦 | t4（主）、t6 |

## 依赖与零交集说明

- `t4 → t2`：两者都改 `tests/notification/test_req_c392_notification_contract.py`（**有文件交集**，无需语义理由）；串行是为了避免同文件并行改。
- `t5 → t1, t3`：t5 扩展 t1/t3 的测试文件（**有文件交集**）。
- `t6 → t5`：**零文件交集**（t6 只产 `verification.md` 与 SQL 证据），语义理由见 `tasks[].dep_reasons`：
  t5 补齐用例后证据链才完整，t6 才能出结单回执。

## 明确不做（继承需求文档「不做什么」）

1. 不定义「何时叫 agent」的判据（D-10 → `REQ-261007133807-eda6`，已派新窗口）；
2. 不修 `risk_stop` 渠道未注册（D-11，用户裁定「② 不需要」）；
3. 不改交易日历数据、不合并各仓飞书机器人、不动 `watch_triggers` 既有台账语义；
4. 不做前端/原型（sides=backend）。

## 未覆盖项处置（引设计文档 §6）

| 未覆盖项 | 处置 |
|---|---|
| `run_forever()` 整环日级跳过 | **t5** 补 |
| `tick()` 跳过留痕去重 | **t5** 补 |
| 异地/手工来源负例 | 不补（需飞书侧信息，属运维核对；设计文档已声明为能力上限） |
| `notification_factory` 装配失败降级 | **t5** 补 |
| `sender_id` host 段一致性（IP vs mDNS） | 不补（已登记为已知瑕疵；跨机分辨不受影响） |
