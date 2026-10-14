# REQ-261007101318-c392 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：四条 FR 全部落地并在生产生效（12:50 重启）；定向 232 passed、key 扫描 621 passed、notify-guard 零外发；审计表两库可用且一条 SQL 可归因来源；卡面契约经用户认可（D-9）。时间型回执（t6）按人工裁定 D-12 以演练替代，强度限定已在验收材料与需求台账声明。24 张卡（6 父 + 18 子）均有 covers 标注，D-1~D-12 逐条交代。

## 1. 验收列表

### v1-1 · FR-1 休市日闸门：tick() 日级收敛到 TradingDayGuard（回填）

**验收内容**：【FR-1 休市日闸门：tick() 日级收敛到 TradingDayGuard（回填）】验收

**操作步骤**：
1. 跑 pytest tests/services/test_watch_engine_trading_day_gate.py -q 得 4 passed
2. 其中必须断言：休市日（冻结 2026-10-07 10:00 且注入 is_trading_day_fn=False）时 tick()==[] 且 repo.calls==0（不判定而非判定后丢弃）、交易日盘中照常产出 1 条事件且 level 非空、交易日 16:00 仍返回 []、未注入时 _resolve_trading_day(2026-10-07) 为 (False, 含 holiday)。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/services/test_watch_engine_trading_day_gate.py -q → 7 passed；_resolve_trading_day 复用恰好 2 处（engine.py:324 / :388）；判定异常两条路径保守判非交易日；变异测试拆门即 1 failed，还原后 7 passed

**验收状态**：✓ 通过

---

### v1-2 · FR-2 名称兜底：禁止把代码当名称（回填）

**验收内容**：【FR-2 名称兜底：禁止把代码当名称（回填）】验收

**操作步骤**：
1. 跑 pytest tests/notification/test_req_c392_notification_contract.py -q 全 passed
2. 其中 test_notifier_never_passes_symbol_as_name 必须断言：打桩 _lookup_stock_name 返回 None 时，传给 facade 的 kwargs['name'] is None（而非 '688525.SH'）
3. test_missing_name_degrades_explicitly_not_to_bare_symbol 断言正文含「名称缺失」。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/notification/test_req_c392_notification_contract.py -v → 10 passed；点名断言 test_notifier_never_passes_symbol_as_name 与 test_missing_name_degrades_explicitly_not_to_bare_symbol 均 PASSED；名称取数并入 PgStockNameResolver（单一口径）

**验收状态**：✓ 通过

---

### v1-3 · FR-3 外发审计 + 来源标识（回填，含建表迁移）

**验收内容**：【FR-3 外发审计 + 来源标识（回填，含建表迁移）】验收

**操作步骤**：
1. ① 两库执行迁移脚本 --apply 后均打印 [verify] 建表完成
2. ② pytest tests/notification/test_notification_audit_repository.py -q 得 4 passed（含 upsert 幂等：同一 notification_id save 两次仍只有 1 行
3. 失败不打挂：save 返回 False 且不上抛）
4. ③ 执行 select occurred_at,title,delivery_channel,delivered,sender_id from quant.notification_audit order by occurred_at desc limit 5 能查回带 sender_id 的行。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：迁移两库 --apply 均 [verify] 建表完成；pytest tests/notification/test_notification_audit_repository.py -q → 5 passed；生产库 psql 查回 sender_id=v2-watch@192.168.1.109#80632（来源可归因）

**验收状态**：✓ 通过

---

### v1-4 · FR-4 文案契约：意图/处置级别 + 闭环承诺解耦（回填）

**验收内容**：【FR-4 文案契约：意图/处置级别 + 闭环承诺解耦（回填）】验收

**操作步骤**：
1. 跑 pytest tests/notification/test_req_c392_notification_contract.py tests/application/test_watch_t12_wiring.py tests/application/test_watch_t12_todo_creation.py tests/application/test_watch_disposition_engine.py -q 全 passed
2. 且必须断言：closed_loop=False 时正文不含「处置入口」与「处置后必有回执」，但含「止损盯盘」与「L1 提醒」
3. entry 与 exit_stop 的正文不相同
4. trigger_level 为空时不出现「**处置**：」。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest 四文件 -q → 35 passed；closed_loop=False 时正文无「处置入口」与「处置后必有回执」但仍含「止损盯盘」「L1 提醒」；entry 与 exit_stop 正文可区分；级别为空隐藏「处置」行

**验收状态**：✓ 通过

---

### v1-5 · 补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级）

**验收内容**：【补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级）】验收

**操作步骤**：
1. 跑 pytest tests/services/test_watch_engine_trading_day_gate.py tests/notification -q 全 passed，且用例总数 ≥ 改动前基线 228（新增用例数 >= 3）
2. 每条新用例失败时能指出具体行为（不得只断言 not raises）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/services/test_watch_engine_trading_day_gate.py tests/notification -q → 94 passed；定向总数 228 → 232（新增 4 条 ≥ 3）；新用例可证伪性经变异测试证明（拆门即转红）

**验收状态**：✓ 通过

---

### v1-6 · 真实交易日回执 + 验收材料（时间型）

**验收内容**：【真实交易日回执 + 验收材料（时间型）】验收

**操作步骤**：
1. 当日执行上述两条 SQL：审计查询返回至少 1 行 watch_triggered 且 sender_id 非空（证明卡片自证来源已落库）
2. watch_triggers 当日有记录（证明引擎在交易日正常判定，未因新闸门而误停）
3. 两组输出已写入 verification.md 并随验收材料提交。若当日无任何触发（规则未命中），须如实记录「当日零触发」并改以手工发一条验证卡的审计行作为替代证据（不得因此判过）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：按人工裁定 D-12 以演练替代真实回执：mock 2026-10-08 tick 产出 1 事件；两条回执 SQL 在可回滚事务中命中（审计 1 行含 feishu/t/sender_id，触发 1 行），ROLLBACK 后残留 0/0；当日复跑两查询均 0 行。强度弱于真实交易日回执，限定见 verification.md 与 D-12

**验收状态**：✓ 通过

---

### v1-7 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：全局 pytest tests -k watch|notification|feishu|alert -q → 621 passed；notify-guard intercepted=0 egress=0；服务 2026-10-07 12:50 重启（trace 1bd0868c）加载新闸门；卡面契约经用户目视认可（D-9）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：12 条裁定逐条兑现：D-1~D-7（立项/出处与发送者取证/范围含 FR-3 溯源）→ 实现见 t1~t4 + verification.md；D-8（渲染级别与闭环解耦 + 审计落渠道层）→ t3/t4；D-9（卡面目视认可）→ 实发卡 notif_ef495a078581464a；D-10（何时叫 agent 另立 REQ-261007133807-eda6，本需求不实现）；D-11（risk_stop 不修也不另立）；D-12（演练替代，强度限定已声明）

**验收状态**：✓ 通过

---

## 2. 测试报告

- pytest tests/services/test_watch_engine_trading_day_gate.py -q → 7 passed（休市日零事件 / 交易日照常 / 盘后仍拦 / 默认闸门认识节假日 / run_forever 整环 / 留痕去重 / 对照组）
- pytest tests/notification/test_req_c392_notification_contract.py -v → 10 passed（含点名两条：name 传 None 而非 symbol；正文含「名称缺失」）
- pytest tests/notification/test_notification_audit_repository.py -q → 5 passed（写入 / upsert 幂等 / 失败不打挂 / 服务层 stamping / 装配失败降级）
- pytest 契约+wiring+todo_creation+disposition_engine 四文件 -q → 35 passed
- pytest tests -k watch|notification|feishu|alert -q → 621 passed / 6143 deselected；notify-guard intercepted=0 egress=0 offenders=[]
- 迁移 20261007_notification_audit_table.py --apply（生产库 + quant_test）→ 两库均 [verify] 建表完成
- psql 查 quant.notification_audit → 1 行真实数据，sender_id=v2-watch@192.168.1.109#80632（非空）
- 变异测试：拆掉 run_forever 日级门 → 1 failed；字节级还原后 7 passed（git diff --stat 仍 +85/-9）
- docs/requirements/REQ-261007101318-c392/reviews/code-review.md：自查式评审（逐条对照设计 + 4 条如实未修项/限定）
- docs/requirements/REQ-261007101318-c392/tests/evidence.md：逐卡命令与输出 + 迁移与库证据 + 变异测试 + t6 演练 SQL + 24 条 covers 覆盖标注
- docs/requirements/REQ-261007101318-c392/notes/t6-receipt-rehearsal.md：mock 2026-10-08 演练记录（ROLLBACK 后残留 0/0）
- docs/requirements/REQ-261007101318-c392/verification.md：交付结论 + 逐条 FR 证据 + D-12 强度限定 + 四条如实局限

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | FR-1 休市日闸门：tick() 日级收敛到 TradingDayGuard（回填） | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-2 | FR-2 名称兜底：禁止把代码当名称（回填） | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-3 | FR-3 外发审计 + 来源标识（回填，含建表迁移） | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-4 | FR-4 文案契约：意图/处置级别 + 闭环承诺解耦（回填） | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-5 | 补齐设计登记的未覆盖用例（run_forever 整环 / 跳过留痕去重 / 装配失败降级） | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-6 | 真实交易日回执 + 验收材料（时间型） | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-7 | 需求级验收 | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544 | 2026-10-07 14:02 |
