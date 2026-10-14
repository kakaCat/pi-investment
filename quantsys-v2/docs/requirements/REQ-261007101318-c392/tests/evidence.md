# 测试证据（REQ-261007101318-c392）

全部命令在 `quantsys-v2/` 下执行；解释器为仓内虚拟环境 `venv/bin/python`（Python 3.13.14）。
**会话末守卫回执恒定**：`notify-guard intercepted=0 egress=0 offenders=[]`（零真实外发）。

## 一、按卡分组的证据

| 卡 | 命令 | 结果 |
|---|---|---|
| t1（FR-1） | `pytest tests/services/test_watch_engine_trading_day_gate.py -q` | **7 passed** |
| t2（FR-2） | `pytest tests/notification/test_req_c392_notification_contract.py -v` | **10 passed**（含点名两条断言） |
| t3（FR-3） | `pytest tests/notification/test_notification_audit_repository.py -v` | **5 passed** |
| t4（FR-4） | `pytest tests/notification/test_req_c392_notification_contract.py tests/application/test_watch_t12_wiring.py tests/application/test_watch_t12_todo_creation.py tests/application/test_watch_disposition_engine.py -q` | **35 passed** |
| t5（补用例） | `pytest tests/services/test_watch_engine_trading_day_gate.py tests/notification -q` | **94 passed**；定向总数 228 → **232** |
| t6（回执） | 两条回执 SQL（见下） | 演练命中；**ROLLBACK 后 0/0** |

## 二、回归与守卫

```bash
venv/bin/python -m pytest tests -k "watch or notification or feishu or alert" -q
# → 621 passed, 6143 deselected, 110 warnings
# → notify-guard intercepted=0 egress=0 offenders=[]
```

## 三、迁移与库证据

```bash
venv/bin/python infrastructure/persistence/migrations/20261007_notification_audit_table.py --apply
venv/bin/python infrastructure/persistence/migrations/20261007_notification_audit_table.py \
    --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test
# → 两库均 [verify] 建表完成

psql -h 127.0.0.1 -U mac -d quant_investment -c \
  "select notification_type,title,delivery_channel,delivered,sender_id from quant.notification_audit;"
# → 1 行：watch_triggered | 盯盘触发 - 688525（审计自检行） | feishu | t | v2-watch@192.168.1.109#80632
```

## 四、变异测试（证明用例可证伪，非空断言）

```text
把 engine.py 中 run_forever 的日级门临时替换为「恒真」：
  test_run_forever_does_not_tick_on_holiday → 1 failed
字节级还原后：7 passed；git diff --stat 仍为 1 file changed, 85 insertions(+), 9 deletions(-)
```

## 五、t6 回执演练（D-12 人工裁定：以演练替代真实回执）

```sql
BEGIN;
INSERT INTO quant.notification_audit  (..., occurred_at='2026-10-08 15:05:00+08', ...);
INSERT INTO quant.watch_triggers      (..., triggered_at='2026-10-08 10:00:00');
SELECT occurred_at,title,delivery_channel,delivered,sender_id
  FROM quant.notification_audit WHERE occurred_at::date='2026-10-08';   -- 1 行
SELECT triggered_at,symbol FROM quant.watch_triggers
 WHERE triggered_at::date='2026-10-08';                                  -- 1 行
ROLLBACK;
-- 回滚后复核：audit 0 / trigger 0（生产库零污染）
```

完整记录：`notes/t6-receipt-rehearsal.md`。**性质**：演练，**不是** 2026-10-08 的真实回执。

## 六、测试口径说明（跨仓模板不一致，如实标注）

自动生成的子卡阶段验收文本写 `npx vitest run tests/` / `pnpm test` / `npx tsc --noEmit`
（属 agent-DH/DSH 仓的 Node 栈）。本仓为 Python/pytest，故按**等价命令**执行：
`venv/bin/python -m pytest …`。本不一致已在每张子卡的汇报中显式写明，卡文本身未改。

## 七、卡片测试覆盖标注（覆盖度门禁口径：逐卡 `covers`）

每一行 = 该卡的测试/证据落点。父卡与其三张子卡（研发/复核/测试）各自独立标注。

### FR-1 休市日闸门（t1）
- t-268fbd（父卡）— `pytest tests/services/test_watch_engine_trading_day_gate.py -q` → 7 passed covers: t-268fbd
- t-dcdeb1（研发）— engine.py 落地 `_resolve_trading_day` 单一入口（+85/-9） covers: t-dcdeb1
- t-b33b0b（复核）— 入口复用恰好 2 处（:324/:388）+ 变异测试拆门即 1 failed covers: t-b33b0b
- t-e58107（测试）— 4 条原始回归锁逐条 PASSED covers: t-e58107

### FR-2 名称兜底（t2）
- t-d5d9b6（父卡）— `pytest tests/notification/test_req_c392_notification_contract.py -v` → 10 passed covers: t-d5d9b6
- t-e5a244（研发）— `notifier.py:190` name=payload.name or None；取数并入 PgStockNameResolver covers: t-e5a244
- t-e75a19（复核）— 口径单一性核查（引擎侧无第二条 get_name）+ 缺失语义 covers: t-e75a19
- t-62e64a（测试）— 点名两条断言（name 传 None / 正文含「名称缺失」）PASSED covers: t-62e64a

### FR-3 外发审计 + 来源标识（t3）
- t-633d3f（父卡）— `pytest tests/notification/test_notification_audit_repository.py -v` → 5 passed + 两库建表 covers: t-633d3f
- t-b2f010（研发）— 仓储/迁移/sender_identity/factory 装配/服务层三处 save covers: t-b2f010
- t-890eb7（复核）— 字段齐备实测 + 失败自吞 + `ON CONFLICT (notification_id)` covers: t-890eb7
- t-e669c6（测试）— 写入/幂等/失败不阻断/服务层 stamping 四条 PASSED covers: t-e669c6

### FR-4 文案契约与闭环解耦（t4）
- t-c76181（父卡）— 四文件 `-q` → 35 passed covers: t-c76181
- t-00bd50（研发）— `_notify_level` 无早退 + closed_loop 随 payload 下发 covers: t-00bd50
- t-2af346（复核）— closed_loop 两态对比 / 级别未知隐藏 / entry≠exit_stop 三条 PASSED covers: t-2af346
- t-7dcdbb（测试）— 三文件 28 passed 汇总 covers: t-7dcdbb

### t5 补未覆盖用例
- t-c926cd（父卡）— 卡内命令 94 passed；总数 228 → 232 covers: t-c926cd
- t-2ae248（研发）— 新增 4 条用例（run_forever 整环 / 留痕去重 / 对照组 / 装配降级） covers: t-2ae248
- t-8ccf53（复核）— 变异测试证明可证伪（拆门 → 1 failed）+ 字节级还原 covers: t-8ccf53
- t-094f32（测试）— 总数口径 ≥ 基线核对 covers: t-094f32

### t6 时间型回执（D-12 演练替代）
- t-2e590d（父卡）— 两条回执 SQL 演练命中 + ROLLBACK 后 0/0 covers: t-2e590d
- t-8d7c74（研发）— mock 2026-10-08 tick 产出 1 事件 + 卡面渲染 + 材料落盘 covers: t-8d7c74
- t-f240da（复核）— 零污染复核（0|0）+ D-12 限定可见性核查 covers: t-f240da
- t-a346aa（测试）— 当日重跑两条 SQL 均 0 行（无演练残留） covers: t-a346aa
