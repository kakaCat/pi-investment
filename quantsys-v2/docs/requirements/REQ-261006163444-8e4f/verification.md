# REQ-261006163444-8e4f 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：数据质量告警三项误报已去伪——口径改为「只在可交易域内判定」，旧两条误报在全市场实跑正文里彻底消失。

已达成（测试证据见 tests/test-evidence.md，含 36 条 covers 覆盖标注）：
① D级计数改 distinct 标的（当天 1207 行 / 404 只；修复前按行计数把单次 403 报成 806）；
② 三项指标改按可交易域统计：域内 5280 只，评分 90.87、覆盖率 98.58%、D级 1 只；「D级 806 过多」「评分 86.28 偏低」不再出现；
③ 检查域按数据事实分三层（可交易 5280 / 观察中 3 / 存量 403，合计 5686），零 DDL、零新增状态、纯函数可单测；
④ 新增「本期掉出可交易域」哨兵：实跑报出 2 只（002813、603183），防止新口径把采集漏批静默豁免；
⑤ 回填只在可交易域内开火；
⑥ 修好审计列 original_count（0 → 60）；
⑦ 阈值随口径重定（D级>20 / 评分<88.0 / 覆盖率信息项 / 回填失败率需分母≥10），task 232 配置 95.0 → 88.0。

实施中另修两处设计稿与实际不符：gap 公式笔误；分域取交易日由 2 个改为 5 个（否则隔 2-4 个交易日的标的被静默丢进存量——实测观察中假报 2 只 / 存量 404 只，修正后 3 / 403）。

诚实交代一项未达标：全市场实跑回填 0/50、All data providers failed 150 条。原假设「剔除退市标的即归零」不成立；真因是 Top-50 为次新/北交所标的，缺失段是窗口起点起的一段，数据源对上市前区间本就取不到。已写入迁移清单与评审报告并给出后续线建议，建议另开需求。

测试与回归：59 条用例全绿（分域 14 + 告警口径 12 + 既有护栏 17 + 异常检测 16），notify-guard 零真实外发；评审报告对四条反例锁做了有效性评级（L1/L2 强，L3/L4 弱并如实标注）。

## 1. 验收列表

### v1-1 · 新增分域纯函数模块 kline_domain.py（契约先行）

**验收内容**：【新增分域纯函数模块 kline_domain.py（契约先行）】验收

**操作步骤**：
1. ① 上述 python -c 导入成功且输出 tradable 含 600519
2. ② grep -c "import psycopg\|from adapters" application/services/kline_domain.py 输出 0（纯函数无 DB 依赖）
3. ③ DomainSnapshot 为 frozen dataclass（尝试赋值抛 FrozenInstanceError）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-2 · 仓储加分域只读方法并把评级计数改为 distinct

**验收内容**：【仓储加分域只读方法并把评级计数改为 distinct】验收

**操作步骤**：
1. ① list_recent_trade_dates(2) 返回 ['2026-09-30','2026-09-29']
2. ② len(list_symbol_last_trade_date()) == 5686
3. ③ count_by_grade_on('D') 等于 select count(distinct symbol) from public.kline_data_quality where created_at::date=current_date and grade='D'（今日 404，不再是 806）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-3 · 服务层返回 per_symbol 全量事实并修 original_count 取键

**验收内容**：【服务层返回 per_symbol 全量事实并修 original_count 取键】验收

**操作步骤**：
1. ① set(res.keys()) ⊇ {'summary','stocks_with_issues','per_symbol'} 且 per_symbol['600519'] 恰含设计规定的 8 键
2. ② 小样本跑完写库后 select original_count from public.kline_data_quality order by created_at desc limit 1 的结果 > 0
3. ③ ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q 全过。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-4 · 作业层接线：域内聚合、新告警判据与回填限域

**验收内容**：【作业层接线：域内聚合、新告警判据与回填限域】验收

**操作步骤**：
1. ① 桩数据（域内 3 只 D、均值 90.84、掉出 3 只）正文含「检查域: 可交易 … / 观察中 … / 存量 …」与「本期掉出可交易域: 3 只」，且不含「D级股票数量过多」「数据质量评分偏低」
2. ② per_symbol 缺省时产出 error 项 qa_scope_unavailable 且 result['alert_scope']=='degraded'
3. ③ ./venv/bin/python -c "import infrastructure.jobs.data_quality_check_job" 无导入错误
4. ④ 桩数据下回填目标 100% 落在 domain.tradable（死标的 0 只）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-5 · 补分域纯函数用例（含 gap 边界与不变量）

**验收内容**：【补分域纯函数用例（含 gap 边界与不变量）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_kline_domain.py -q 全过且用例数 ≥ 7
2. 其中 T5 断言 degraded is True 且无异常抛出、T7 断言并集等于 set(gap_days) 且三集合两两不相交。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-6 · 补告警口径用例与四条反例锁

**验收内容**：【补告警口径用例与四条反例锁】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/test_data_quality_alert_scope.py tests/test_data_quality_job_guardrails.py -q 全过
2. ② 任务汇报里附 L1-L4 改前红/改后绿的两次输出（L1 改前返回 806、L3 改前 original_count==0、L4 改前目标含 5 只已退市），缺一即视为锁无效。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-7 · 变更 task 232 阈值配置并实跑复验出证据

**验收内容**：【变更 task 232 阈值配置并实跑复验出证据】验收

**操作步骤**：
1. ① 正文出现检查域计数、掉出名单、统计 N/N 只三段，且不含「D级股票数量过多」「数据质量评分偏低」
2. ② 最新 run 记录的 result 里 alert_scope 为 tradable、domain.tradable_count 约 5280
3. ③ 复验窗口内 grep -c "All data providers failed" logs/api.log 等于 0（今日基线 374）
4. ④ 新写入行 original_count > 0
5. 四个输出原样贴进任务汇报。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-8 · 落盘迁移、兼容与回滚清单

**验收内容**：【落盘迁移、兼容与回滚清单】验收

**操作步骤**：
1. ① 文档五节齐全且每节指到具体文件/行
2. ② grep -c "零 schema" docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md ≥ 1
3. ③ 旧调用方清单条数与 grep -rn "check_data_quality(" --include='*.py' 的命中数一致（9 处，含定义与同名异类）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-9 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

## 2. 测试报告

- pytest tests/test_kline_domain.py tests/test_data_quality_alert_scope.py tests/test_data_quality_job_guardrails.py tests/test_data_validator_anomaly_detection.py -q → 59 passed；notify-guard intercepted=0 egress=0
- 分域复算：build_domain_snapshot(KlineORMRepository()) → tradable 5280 / observing 3 / stock 403，掉出名单 ['002813','603183']（SQL 独立复算一致）
- 重复计数实证：public.kline_data_quality 当天 grade='D' 共 1207 行 / 404 只 —— 修复前按行计数把单次 403 报成 806
- count_by_grade_on('D') 改为 distinct 后返回 404，与 count(distinct symbol) 相等
- 全市场实跑（16:51–16:53，5686 只）：alert_scope=tradable；domain={tradable 5280, observing 3, stock 403, stats_symbols 5280, partial false, degraded false}
- 全市场实跑告警正文三段齐（检查域计数 / 本期掉出 2 只 / 域内指标 评分 90.87、覆盖率 98.58%、D级 1 只），且不含旧两条误报
- 审计列：新写入行 original_count = 60（窗口交易日数），修复前恒为 0
- 配置行：quant.scheduler_tasks id=232 的 params.quality_threshold 已由 95.0 改为 88.0（旧值留痕可回滚）
- 负向契约：run 结果中 per_symbol 不存在（实测 False）
- 降级路径用例 test_t17 / test_t17b 均绿（error 项 qa_scope_unavailable，不回退第二真相源）
- docs/requirements/REQ-261006163444-8e4f/tests/test-evidence.md（59 passed 输出、SQL 复算、实跑字段与正文、36 条 covers 覆盖标注）
- docs/requirements/REQ-261006163444-8e4f/reviews/review.md（逐条 FR 复核、反例锁有效性评级、未覆盖部分）
- docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md（零 schema 变更声明、旧调用方核对、配置旧值与回滚、实跑复验、后续线）
- docs/requirements/REQ-261006163444-8e4f/design/（架构 / 数据模型 / 接口 / 测试用例 / 使用场景 五份）
- ⚠️ 未达标项：回填失败率一条 —— 全市场实跑回填 0/50、All data providers failed 150 条。真因是 Top-50 为 920xxx/688xxx 次新与北交所标的，其缺失段是窗口起点起的一段，数据源对上市前区间本就取不到（与原假设不同）。已登记根因与三条后续线建议，建议另开需求

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 新增分域纯函数模块 kline_domain.py（契约先行） | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:05 |
| v1-2 | 仓储加分域只读方法并把评级计数改为 distinct | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:04 |
| v1-3 | 服务层返回 per_symbol 全量事实并修 original_count 取键 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:04 |
| v1-4 | 作业层接线：域内聚合、新告警判据与回填限域 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:04 |
| v1-5 | 补分域纯函数用例（含 gap 边界与不变量） | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:04 |
| v1-6 | 补告警口径用例与四条反例锁 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:05 |
| v1-7 | 变更 task 232 阈值配置并实跑复验出证据 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:05 |
| v1-8 | 落盘迁移、兼容与回滚清单 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:05 |
| v1-9 | 需求级验收 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:05 |
| v1-10 | 需求级验收 | ✓ 通过 | human/session-efbdbfc6-d84c-4d09-9829-b1c906699db5 | 2026-10-06 17:05 |
