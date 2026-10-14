---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# 测试用例设计（REQ-261007133807-eda6）

> 判据一律可跑：跑什么命令 / 看什么读数 / 什么取值算过。

## 测试策略 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

- **域层穷举**：裁决是纯函数 → 15 条判据逐行真值表（既有 `tests/domain/test_level_router.py` 的打法）；
- **兼容锁优先**：既有 `test_escalation_checker.py` / `test_watch_disposition.py` / `test_metric_contract.py`
  **一行不改**，它们就是"收敛没改行为"的证据；
- **两条渲染路径对拍**：同一组变量分别喂两个 formatter，断言两边的「升级原因」行同形；
- **端到端用冻结输入**：不依赖真实交易日与真实外发（沿用 `REQ-261007101318-c392` 的冻结时钟/桩打法，
  且遵守本仓通知外发守卫：不真实外发）。

## 功能测试用例 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 用例 id | 层级 | 判据（跑什么、看什么） | 期望读数 | serves |
|---|---|---|---|---|
| TC-1 | 单元 | `pytest tests/services/test_watch_escalation_verdict.py -q` | 15 条判据逐行命中对应码（含四道门与预算的"没叫"码）；`should_wake` 与码一致 | FR-1 |
| TC-2 | 单元 | 同 TC-1 文件内跨调用方用例 | 同一输入经 IF-1 / IF-3 / IF-4 三条入口，`code` 与 `path` **逐字段相同** | FR-1 |
| TC-3 | 单元（兼容锁） | `pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py tests/application/test_watch_disposition.py -q` | **全绿且用例未改**（文案与语义逐字不变） | FR-1 |
| TC-4 | 集成 | `pytest tests/services/test_watch_trigger_escalation_columns.py -q` | `record()` 落两列；`deduped` / `auto_observed` 行**也有码**（非 NULL） | FR-2 |
| TC-5 | 集成 | `pytest tests/notification/test_watch_escalation_reason_line.py -q` | 旧渲染与分级渲染各出「升级原因」行且同形；无理由时该行**不出现** | FR-3 |
| TC-6 | 集成 | `pytest tests/domain/test_escalation_policy_defaults.py tests/adapters/test_watch_rules_api_policy.py -q` | 不传策略 → 落库为 `{"auto_escalate": true, "anomaly_change_pct": 5.0}`；`GET` 回 `escalation_explain` 非空且含「会叫我」语义 | FR-4 |
| TC-7 | E2E | `pytest tests/application/test_watch_escalation_e2e.py -q`（冻结时钟 + 桩外发） | 一次触发后：① 触发记录带码与理由；② 卡面正文含「升级原因」；③ 外发守卫 `intercepted` 记账为声明值（零真实外发） | FR-1、FR-2、FR-3 |
| TC-8 | 静态 | `grep -rn "=='L2'\|== \"L2\"" application/ domain/ \| grep -v level_resolver \| grep -v escalation_verdict`；`grep -rn "触发频率异常" application/ domain/ docs/architecture/ \| grep -v docs/requirements` | 两条 grep 均 **0 命中** | FR-1、FR-5 |
| TC-9 | 集成（回归锁） | `pytest tests/application/test_watch_disposition_engine.py tests/services/test_watch_engine.py -q` | 全绿；同输入下 `disposition == 'escalated'` 条数与改造前**一致**（唤醒量不增） | FR-1、FR-2 |
| TC-10 | 迁移 | `python infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py --apply --dsn <测试库>` 后 `pytest tests/test_orm_db_drift.py -q` | 退出码 0；漂移门禁全绿（两库都已加列） | FR-2 |

### TC-1 真值表（判据明细） `serves: FR-1`

```
输入（rule × condition × quote × gate）                 期望 code                  should_wake
intent=exit_stop（任意 gate，预算已耗尽）                CONSTITUTIONAL_INTENT      True
daily_wake_count=8 >= budget=8 且 intent=entry            BUDGET_EXHAUSTED          False
L1 + action_hint.escalate=true                            RULE_EXPLICIT_ESCALATE    True
L1 + |change_pct|=6.1 >= 5.0                              ANOMALY_CHANGE_PCT        True
L1 + auto_escalate=false + |change_pct|=6.1               （落到五道门，见下）       取决动作
L2 规则（trigger_level=L2）                               RULE_LEVEL_L2             True
trigger_kind=meta（轻门过）                               META_REVIEW               True
intent=trend_observe                                      OBSERVE_INTENT            False
amount=50 < 100000×1%=1000                                AMOUNT_BELOW_THRESHOLD    False
last_intervention_at=now-1h                               SAME_TOPIC_COOLDOWN       False
expected_value=1 < 3×1.0                                  ECONOMIC_BELOW_K          False
action_on_trigger=buy（各门通过）                          GATES_PASSED_ACTION       True
action_on_trigger=observe 但 intent 为空且非观察类          PENDING_NO_ACTION         False
去重命中（裁决后覆盖）                                     DEDUPED                   False
抑噪期（裁决后覆盖）                                       SUPPRESSED                False
输入缺省/未接入                                           UNKNOWN                   False
```

## 测试覆盖度统计 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 条款 | 覆盖用例 | 覆盖了什么 |
|---|---|---|
| FR-1 | TC-1、TC-2、TC-3、TC-7、TC-8、TC-9 | 单一口径、跨入口一致、兼容锁、无第二处判定 |
| FR-2 | TC-4、TC-7、TC-10 | 两列落库、"没叫"也有码、迁移 |
| FR-3 | TC-5、TC-7 | 两条渲染路径都写、无理由隐藏 |
| FR-4 | TC-6 | 缺省显式化 + 只读回显 + 存量不拒 |
| FR-5 | TC-8 | 陈旧文案归零、判据表与码表同源 |

> **未覆盖/需人工**：无（本需求不涉及界面视觉与线下流程）。
> 判据 6（陈旧文案）与判据 2（结构）是**静态判据**，由拆分阶段的验收卡直接执行。

## 关键决策与取舍 `serves: FR-1, FR-2`

1. **不写"锚点式"断言**（如断言日志中出现某句中文）：断言落在**码**上（受控词表），
   中文文案可读性调整不会让测试假红。
2. **兼容锁用例保持原样**：如果实施中发现必须改既有用例才能过，说明行为变了 —— 停下来重新评估，
   不许"顺手改测试"。
3. **E2E 用桩外发**：本仓有通知外发守卫（`tests/notify_guard.py`），E2E 必须声明期望的拦截计数，
   零真实外发 —— 这是硬要求，不是风格偏好。

## 技术方案与亮点 `serves: FR-2, FR-3`

- **一条 SQL 的验收**：TC-4/TC-7 的断言最终都可归结为一句话查询（判据 3），
  排障者不必读代码即可回答"为什么叫/没叫"。
- **两条渲染路径对拍**：同一变量表喂两个 formatter，把"两条路都要写"变成可执行断言，
  而不是靠 code review 记得。
