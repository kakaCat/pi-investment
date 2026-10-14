# 测试证据（REQ-261007133807-eda6）

全部命令在 `quantsys-v2/` 下执行；解释器为仓内虚拟环境 `venv/bin/python`（Python 3.13.14）。
**会话末守卫回执恒定**：`notify-guard intercepted=0 egress=0 offenders=[]`（零真实外发）。

## 一、按卡分组的证据

| 卡 | 命令 | 结果 |
|---|---|---|
| t1（FR-1/FR-2） | `pytest tests/services/test_watch_escalation_verdict.py -q -k code_table` | **4 passed**；另 `python -c` 断言 `len(ALL)==15` 且 `PATH_LABEL` 覆盖全部 → exit 0 |
| t2（FR-1） | `pytest tests/services/test_watch_escalation_verdict.py -q` | **26 passed**（15 行判据 + 跨入口一致 + metric 抛错） |
| t3（FR-4） | `pytest tests/domain/test_escalation_policy_defaults.py -q` | **10 passed**（default 显式化 + `to_dict` + 六分支说明） |
| t4（FR-1） | `pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py -q` | **20 passed**，且两个测试文件 `git status` 零改动 |
| t5（FR-1） | `pytest tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py tests/application/test_watch_disposition_verdict.py -q` | **29 passed** |
| t6（FR-1/FR-2） | `pytest tests/services/test_watch_engine_escalation_wiring.py tests/services/test_watch_engine.py -q` | **43 passed**（含真实双规则去重 → DEDUPED + 原判） |
| t7（FR-2） | 迁移两库 `--apply`；`pytest tests/test_orm_db_drift.py -q` | exit 0（幂等复跑通过）；**6 passed** |
| t8（FR-2） | `pytest tests/services/test_watch_trigger_escalation_columns.py -q` | **6 passed**（deduped/auto_observed 行码非 NULL；写库失败不阻断通知） |
| t9（FR-3） | `pytest tests/notification/test_watch_escalation_reason_line.py -q` | **10 passed**（两条渲染路径同形；非唤醒卡不渲染该行） |
| t10（FR-4） | `pytest tests/adapters/test_watch_rules_api_policy.py -q` | **12 passed**（含库回读 == `{'auto_escalate': True, 'anomaly_change_pct': 5.0}`） |
| t11（FR-4） | `pytest tests/adapters/test_watch_rules_api_policy.py -q -k explain` | **2 passed**（存量 NULL 读后仍 NULL） |
| t12（FR-5） | `pytest tests/services/test_watch_contract_parity.py -q` | **4 passed**（契约文档 == 设计文档 == 代码码表，15 条） |
| t13（FR-1~FR-5） | `pytest tests/application/test_watch_escalation_e2e.py -q` | **5 passed**；notify-guard `intercepted=0 egress=0` |

## 二、回归与守卫

```bash
venv/bin/python -m pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py \
  tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py \
  tests/services/test_watch_engine.py tests/application/test_watch_escalation_e2e.py \
  tests/services/test_watch_engine_escalation_wiring.py -q
# → 92 passed, 13 warnings
# → notify-guard intercepted=0 egress=0 offenders=[]

venv/bin/python -m pytest tests/notification -q
# → 93 passed

venv/bin/python -m pytest tests/api/test_watch_routes_async.py tests/adapters/test_watch_rules_api_policy.py -q
# → 30 passed
```

**唤醒量回归锁**（本需求只做收敛与可见化，不放松也不收紧）：

```bash
venv/bin/python -m pytest tests/application/test_watch_escalation_e2e.py -q -k wake_count
# → 1 passed：4 条规则里恰好 2 条进 agent 队列（disposition=escalated），2 条 auto_observed
```

**结构判据**（无第二处独立 L2 判定 / 陈旧文案归零）：

```bash
venv/bin/python -m pytest tests/application/test_watch_escalation_e2e.py -q -k "l2_wake or stale_removed"
# → 2 passed（L2 比较点白名单：3 处皆"按已定级别选渠道/优先级"的路由）

grep -rn "触发频率异常" application/ domain/ docs/architecture/   # → 0 命中
```

## 三、迁移与库证据

```bash
PYTHONPATH=. venv/bin/python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py \
  --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test        # → exit 0，两列存在（0 行）
PYTHONPATH=. venv/bin/python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py \
  --apply --dsn postgresql://mac@127.0.0.1:5432/quant_investment  # → exit 0，两列存在（89 行历史行 NULL）
# 幂等复跑（测试库）→ [跳过] 两列均已存在（幂等）
```

三列/两列对拍（ORM ↔ 两库 schema）：

```bash
venv/bin/python -c "..."   # ORM 两列类型 TEXT；两库 information_schema 均含两列且 is_nullable=YES
# → OK: ORM 与两库 schema 一致，且均为可空
```

**测试库清洁**（用例自清理，不留痕）：

```bash
psql -h 127.0.0.1 -U mac -d quant_test -c "select (select count(*) from quant.watch_rules) as rules, (select count(*) from quant.watch_triggers) as triggers;"
# → rules 0 | triggers 0
```

## 四、新增/扩展用例计数

| 文件 | 用例数 |
|---|---|
| `tests/services/test_watch_escalation_verdict.py` | 26（新建） |
| `tests/services/test_watch_engine_escalation_wiring.py` | 6（新建） |
| `tests/services/test_watch_trigger_escalation_columns.py` | 6（新建） |
| `tests/services/test_watch_contract_parity.py` | 4（新建） |
| `tests/notification/test_watch_escalation_reason_line.py` | 10（新建） |
| `tests/domain/test_escalation_policy_defaults.py` | 10（新建） |
| `tests/adapters/test_watch_rules_api_policy.py` | 12（新建） |
| `tests/application/test_watch_disposition_verdict.py` | 5（新建） |
| `tests/application/test_watch_escalation_e2e.py` | 5（新建） |
| `tests/application/test_watch_disposition_engine.py` | 1 处替身签名跟进（断言未变） |
| **合计新增** | **84** |

## 五、未覆盖 / 需人工项

- **界面目视**：本需求 `sides=[backend]`，无前端页面产出，**不涉界面目视**。
- **真实外发观察**：卡面由本地渲染器渲染并断言（不真实外发，`notify-guard` 保证）；
  "真实飞书卡长什么样"需在下次真实触发时目视确认 —— 这是时间型条件，非本卡代码判据。
- **P2/P3 聚合摘要未含该行**：见 `reviews/code-review.md` 发现 2（已登记，未修）。

## 六、任务 ↔ 测试覆盖对照（逐任务 `covers` 标注）

> 说明：子卡的四个阶段（研发/联调/复核/测试）各自的可证伪读数写在**卡文档**里
> （`tasks/<id>.md`）；本表登记的是"这张卡的产出被哪条测试判据覆盖"。

| 任务 | 角色 | 覆盖它的测试 | 读数 |
|---|---|---|---|
| t-d24cfb | 父卡 | `tests/services/test_watch_escalation_verdict.py -k code_table` covers: t-d24cfb | 4 passed |
| t-339754 | 子卡 | `tests/services/test_watch_escalation_verdict.py -k code_table` covers: t-339754 | 4 passed |
| t-17bdf7 | 子卡 | `tests/services/test_watch_escalation_verdict.py -k code_table` covers: t-17bdf7 | 4 passed |
| t-53b2de | 子卡 | `tests/services/test_watch_escalation_verdict.py -k code_table` covers: t-53b2de | 4 passed |
| t-a60ba4 | 子卡 | `tests/services/test_watch_escalation_verdict.py -k code_table` covers: t-a60ba4 | 4 passed |
| t-2f1402 | 父卡 | `tests/services/test_watch_escalation_verdict.py` covers: t-2f1402 | 26 passed |
| t-d9eb91 | 子卡 | `tests/services/test_watch_escalation_verdict.py` covers: t-d9eb91 | 26 passed |
| t-1d6cdd | 子卡 | `tests/services/test_watch_escalation_verdict.py` covers: t-1d6cdd | 26 passed |
| t-e67b0f | 子卡 | `tests/services/test_watch_escalation_verdict.py` covers: t-e67b0f | 26 passed |
| t-fff73f | 子卡 | `tests/services/test_watch_escalation_verdict.py` covers: t-fff73f | 26 passed |
| t-761703 | 父卡 | `tests/test_orm_db_drift.py（+ 迁移脚本 --apply 两库）` covers: t-761703 | 6 passed / exit 0 |
| t-9b357b | 子卡 | `tests/test_orm_db_drift.py（+ 迁移脚本 --apply 两库）` covers: t-9b357b | 6 passed / exit 0 |
| t-6aad65 | 子卡 | `tests/test_orm_db_drift.py（+ 迁移脚本 --apply 两库）` covers: t-6aad65 | 6 passed / exit 0 |
| t-7317cc | 子卡 | `tests/test_orm_db_drift.py（+ 迁移脚本 --apply 两库）` covers: t-7317cc | 6 passed / exit 0 |
| t-1e0992 | 子卡 | `tests/test_orm_db_drift.py（+ 迁移脚本 --apply 两库）` covers: t-1e0992 | 6 passed / exit 0 |
| t-152a0b | 父卡 | `tests/domain/test_escalation_policy_defaults.py` covers: t-152a0b | 10 passed |
| t-176084 | 子卡 | `tests/domain/test_escalation_policy_defaults.py` covers: t-176084 | 10 passed |
| t-3f6454 | 子卡 | `tests/domain/test_escalation_policy_defaults.py` covers: t-3f6454 | 10 passed |
| t-c1b8a8 | 子卡 | `tests/domain/test_escalation_policy_defaults.py` covers: t-c1b8a8 | 10 passed |
| t-6e3c11 | 子卡 | `tests/domain/test_escalation_policy_defaults.py` covers: t-6e3c11 | 10 passed |
| t-fa9574 | 父卡 | `tests/services/test_escalation_checker.py + test_metric_contract.py` covers: t-fa9574 | 20 passed |
| t-7713e4 | 子卡 | `tests/services/test_escalation_checker.py + test_metric_contract.py` covers: t-7713e4 | 20 passed |
| t-a08bf2 | 子卡 | `tests/services/test_escalation_checker.py + test_metric_contract.py` covers: t-a08bf2 | 20 passed |
| t-38caaa | 子卡 | `tests/services/test_escalation_checker.py + test_metric_contract.py` covers: t-38caaa | 20 passed |
| t-70b182 | 子卡 | `tests/services/test_escalation_checker.py + test_metric_contract.py` covers: t-70b182 | 20 passed |
| t-2fbc40 | 父卡 | `tests/application/test_watch_disposition{,_engine,_verdict}.py` covers: t-2fbc40 | 29 passed |
| t-8fd357 | 子卡 | `tests/application/test_watch_disposition{,_engine,_verdict}.py` covers: t-8fd357 | 29 passed |
| t-5a3bc9 | 子卡 | `tests/application/test_watch_disposition{,_engine,_verdict}.py` covers: t-5a3bc9 | 29 passed |
| t-7c7aef | 子卡 | `tests/application/test_watch_disposition{,_engine,_verdict}.py` covers: t-7c7aef | 29 passed |
| t-dd547b | 子卡 | `tests/application/test_watch_disposition{,_engine,_verdict}.py` covers: t-dd547b | 29 passed |
| t-08d545 | 父卡 | `tests/services/test_watch_engine_escalation_wiring.py + test_watch_engine.py` covers: t-08d545 | 43 passed |
| t-528cc7 | 子卡 | `tests/services/test_watch_engine_escalation_wiring.py + test_watch_engine.py` covers: t-528cc7 | 43 passed |
| t-b5a2f9 | 子卡 | `tests/services/test_watch_engine_escalation_wiring.py + test_watch_engine.py` covers: t-b5a2f9 | 43 passed |
| t-0b0f61 | 子卡 | `tests/services/test_watch_engine_escalation_wiring.py + test_watch_engine.py` covers: t-0b0f61 | 43 passed |
| t-90f6dc | 子卡 | `tests/services/test_watch_engine_escalation_wiring.py + test_watch_engine.py` covers: t-90f6dc | 43 passed |
| t-fc92ab | 父卡 | `tests/services/test_watch_trigger_escalation_columns.py` covers: t-fc92ab | 6 passed |
| t-b3dcd8 | 子卡 | `tests/services/test_watch_trigger_escalation_columns.py` covers: t-b3dcd8 | 6 passed |
| t-4e7a83 | 子卡 | `tests/services/test_watch_trigger_escalation_columns.py` covers: t-4e7a83 | 6 passed |
| t-c31200 | 子卡 | `tests/services/test_watch_trigger_escalation_columns.py` covers: t-c31200 | 6 passed |
| t-ee89ed | 子卡 | `tests/services/test_watch_trigger_escalation_columns.py` covers: t-ee89ed | 6 passed |
| t-ba3f1f | 父卡 | `tests/notification/test_watch_escalation_reason_line.py` covers: t-ba3f1f | 10 passed |
| t-0fb46d | 子卡 | `tests/notification/test_watch_escalation_reason_line.py` covers: t-0fb46d | 10 passed |
| t-56465e | 子卡 | `tests/notification/test_watch_escalation_reason_line.py` covers: t-56465e | 10 passed |
| t-6ed558 | 子卡 | `tests/notification/test_watch_escalation_reason_line.py` covers: t-6ed558 | 10 passed |
| t-0f1e0e | 子卡 | `tests/notification/test_watch_escalation_reason_line.py` covers: t-0f1e0e | 10 passed |
| t-9cd059 | 父卡 | `tests/adapters/test_watch_rules_api_policy.py` covers: t-9cd059 | 12 passed |
| t-07f5f0 | 子卡 | `tests/adapters/test_watch_rules_api_policy.py` covers: t-07f5f0 | 12 passed |
| t-a2c6e5 | 子卡 | `tests/adapters/test_watch_rules_api_policy.py` covers: t-a2c6e5 | 12 passed |
| t-2dc03f | 子卡 | `tests/adapters/test_watch_rules_api_policy.py` covers: t-2dc03f | 12 passed |
| t-f7cd30 | 子卡 | `tests/adapters/test_watch_rules_api_policy.py` covers: t-f7cd30 | 12 passed |
| t-7c7d38 | 父卡 | `tests/adapters/test_watch_rules_api_policy.py -k explain` covers: t-7c7d38 | 2 passed |
| t-e717ca | 子卡 | `tests/adapters/test_watch_rules_api_policy.py -k explain` covers: t-e717ca | 2 passed |
| t-7631f6 | 子卡 | `tests/adapters/test_watch_rules_api_policy.py -k explain` covers: t-7631f6 | 2 passed |
| t-3e6466 | 子卡 | `tests/adapters/test_watch_rules_api_policy.py -k explain` covers: t-3e6466 | 2 passed |
| t-8a6ce5 | 子卡 | `tests/adapters/test_watch_rules_api_policy.py -k explain` covers: t-8a6ce5 | 2 passed |
| t-435423 | 父卡 | `tests/services/test_watch_contract_parity.py` covers: t-435423 | 4 passed |
| t-c19f4f | 子卡 | `tests/services/test_watch_contract_parity.py` covers: t-c19f4f | 4 passed |
| t-a85be6 | 子卡 | `tests/services/test_watch_contract_parity.py` covers: t-a85be6 | 4 passed |
| t-8097f7 | 父卡 | `tests/application/test_watch_escalation_e2e.py` covers: t-8097f7 | 5 passed |
| t-1e2f5e | 子卡 | `tests/application/test_watch_escalation_e2e.py` covers: t-1e2f5e | 5 passed |
