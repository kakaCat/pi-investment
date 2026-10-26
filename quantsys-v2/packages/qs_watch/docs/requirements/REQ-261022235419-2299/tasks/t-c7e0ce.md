# t-c7e0ce 数据迁移：trigger_channel/process_state/cycle_count + engine 标记·研发

> 需求：REQ-261022235419-2299 盯盘引擎 V2 —— 持仓驱动重写

## 在做什么
数据迁移：trigger_channel/process_state/cycle_count + engine 标记·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-23T03:45:40.043Z，窗口 707d8732-069e-48fa-879b-4cae446b186e）

新建迁移 20261023_watch_rules_v2_routing.py 并双库执行成功：watch_rules 加 trigger_channel/process_state/cycle_count 三列（+CHECK+注释+存量回填），生产库与 quant_test 均 VERIFY OK，psql 复核默认值 agent/pending/0。注：验收模板中的 `npx vitest run tests/` 为 reqboard 通用样板——本仓（Python 项目，qs_watch 工作区无 package.json/tests JS 套件）不存在 vitest 测试面，以 py_compile + 真实 dry-run/双库 apply + psql 断言替代。

### 完成项

- 新建迁移文件 20261023_watch_rules_v2_routing.py（沿用 20261022 模板）
- 三列 ADD COLUMN IF NOT EXISTS：trigger_channel VARCHAR(16) NOT NULL DEFAULT 'agent' / process_state VARCHAR(16) NOT NULL DEFAULT 'pending' / cycle_count INTEGER NOT NULL DEFAULT 0
- 三条 CHECK 约束（DO 块幂等包裹）：watch_rules_trigger_channel_chk(agent,direct) / watch_rules_process_state_chk(pending,processed) / watch_rules_cycle_count_chk(0..9)
- 三条列注释落库（psql col_description 验证 has_comment=t × 3）
- 存量回填：默认值自动覆盖存量行 + 3 条防御性 UPDATE（实际 0 行，幂等）
- dry-run 通过；生产库 quant_investment --apply → VERIFY OK
- quant_test 库 --apply → VERIFY OK
- psql 验证双库：三列存在、NOT NULL、默认值 agent/pending/0、4 条 watch_rules_*_chk 约束齐全

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/infrastructure/persistence/migrations/20261023_watch_rules_v2_routing.py`

---
## 汇报 2（2026-10-23T03:46:58.715Z，窗口 707d8732-069e-48fa-879b-4cae446b186e）

第 2 次认领复验：迁移文件已被更新为含 engine 标记列（engine VARCHAR(8) DEFAULT 'v1'，影子期双写对账用），已对 quant_investment 与 quant_test 双库重新 --apply（幂等），psql 复核四列 trigger_channel/process_state/cycle_count/engine 默认值 agent/pending/0/v1 全部就位，VERIFY OK。验收样板 npx vitest 不适用（Python 仓），以真实 dry-run/apply/psql 断言为凭证。

### 完成项

- 复跑（第 2 次认领）：确认迁移文件已被链/lead 更新为含 engine 标记列（engine VARCHAR(8) NOT NULL DEFAULT 'v1'，backend.md 影子期双写对账）
- 以更新后的文件对 quant_investment 重跑 --apply（幂等：ADD COLUMN IF NOT EXISTS/DO 块查重）→ VERIFY OK
- 对 quant_test 重跑 --apply → VERIFY OK
- psql 复核双库：四列存在且默认值 agent/pending/0/v1；CHECK 约束齐全（trigger_channel/process_state/cycle_count/rule_state 四条 chk）
- 存量回填 4 条 UPDATE 均 0 行（历史数据无异常值）

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/infrastructure/persistence/migrations/20261023_watch_rules_v2_routing.py`

---
