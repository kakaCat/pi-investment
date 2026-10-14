# REQ-261006190953-fc43 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：「净值序列只认交易日」这条口径已在四层落地并通过代码侧验收：① 写入端——净值仓储成为唯一写入闸门，休市日拒写并留痕（真库实测：周末/周日/国庆假期的写入请求一行都不落库，日历降级时照写并标注）；② 读取端——归因与风险指标窗口按交易日取数，days 语义改为交易日数，并显式带出 window（起止/交易日数/被过滤行数/来源）与 nav_coverage（缺口）；③ 缺口判断从 agent-dh 搬到 v2（持有日历的一侧），agent-dh 改为只消费、缺数据时如实声明「未做交易日校验」而不再用工作日自算——旧口径在同一段序列上报 21 个假缺口（含国庆）；④ 存量——清理迁移可 dry-run/幂等/回滚，按实施期裁定 D-6 改为白名单语义后在生产 dry-run 命中 35 行、重算 65 行派生字段、库内零改动；另有常驻巡检把「库里还有没有非交易日行」变成退出码判据（当前生产如实报红：35 行 / 退出码 2）。

代码侧证据：v2 新增与改动测试 117 passed；邻域回归 391 passed / 0 failed；agent-dh 15 passed。**两项需人工放行后才能说端到端成立**：① 生产数据清理未执行（只跑了 dry-run）；② v2 API 未重启，接口新字段尚未在 5001 生效（现场核对仍只有 5 个旧键）——重启会把其他需求在飞的未提交改动一并投上生产，属跨需求部署决定，故本窗口不擅自执行。

本轮抓到 4 个真问题并都已处置：设计删除谓词与日历数据模型不符（D-6）、既有测试隐含假设「今天一定是交易日」（改夹具）、新增代码引入的显式 returns 口径 500（修+回归锁）、一条把未实现缓解写成既成事实的过时注释（订正，且改文字而不放松 grep 判据）。

已知红且非本需求造成：分层棘轮 tests/test_layer_purity.py 实测 320 > 基线 318；逐文件归因后本需求占 +1（闸门设在仓储写入函数的结构性代价，替代方案会重新打开「漏加门」的洞），他人在飞占 +1；未调基线。实施期共记录 15 处偏离与 7 条残余风险，全部落在 notes/implementation-deviations.md 供逐项复核。测试证据含 35 张任务卡的 covers 标注。

## 1. 验收列表

### v1-1 · 落 nav_series 口径模块与契约（并留 shim 保导入兼容）

**验收内容**：【落 nav_series 口径模块与契约（并留 shim 保导入兼容）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_nav_series.py -q 全过，且至少断言：① trading_day_set() 在日历表空/查询异常时返回 None（不是 set()）
2. ② filter_trading_days(rows, None) 返回全量行
3. ③ 传入含 09-05(六)/09-06(日) 行的序列后收益条数 = 交易日数 - 1
4. ④ 跨节假日的涨跌归到复市首日那一段（09-30→10-08 只产出一条收益）
5. ⑤ 覆盖 09-30→10-08 时 nav_coverage 的 missing_count == 0
6. ⑥ 缺 2026-09-25（真交易日）时 missing_count == 1
7. ⑦ trading_days=None 时 verified is False 且 missing_count == 0
8. ⑧ from application.services.risk_metrics_service import nav_returns_from_snapshots 仍可导入且行为与 nav_series 一致。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-2 · 给净值仓储加唯一写入闸门，并让日收益基准按交易日回退

**验收内容**：【给净值仓储加唯一写入闸门，并让日收益基准按交易日回退】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_equity_snapshot_trading_day_gate.py tests/test_equity_snapshot_daily_return.py -q 全过，且至少断言：① 休市日（2026-09-05 / 2026-10-02）调 upsert_equity_snapshot 返回 None 且这些日期在表中零行
2. ② 交易日（2026-09-30）正常落库且 daily_return 非 NULL
3. ③ 日历降级（degraded=True）时照写且返回值/日志带 degraded
4. ④ force=True 可写入非交易日行（显式旁路）
5. ⑤ get_equity_snapshots(trading_days_only=True, limit=N) 返回条数 == 交易日数 N，尾部日期落在日历上
6. ⑥ trading_days=None 时不过滤（退回现行行为）
7. ⑦ previous_valid_snapshot(before=2026-10-08, trading_days=...) 返回 2026-09-30 而不是 2026-10-02
8. ⑧ total_value<cash 的残缺快照仍被跳过。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-3 · 接线两处写入入口：非交易日拒写并留痕 refused/skipped

**验收内容**：【接线两处写入入口：非交易日拒写并留痕 refused/skipped】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_equity_snapshot_trading_day_gate.py -q 全过，且至少断言：① 休市日 snapshot_all_accounts 返回 written=0 且 refused=n（n=活跃账户数）并带五键 trading_day
2. ② 交易日返回 written=n 且 refused=0
3. ③ take_daily_snapshot 在休市日返回 skipped 结构且不抛异常（snap=None 路径被覆盖）
4. ④ EquitySnapshotJob.run 休市日 skipped=True，reason 与“未收盘”可区分
5. ⑤ 该日 K 线存在但日历判休市时仍跳过（证明 _has_bar 已不是交易日判据）
6. ⑥ 打桩 trading_day_gate.skip_non_trading_day 后断言两条路径都被调用过（防各自另写判定）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-4 · 读取端接线：days 改为交易日数并返回 window 与 nav_coverage

**验收内容**：【读取端接线：days 改为交易日数并返回 window 与 nav_coverage】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_risk_metrics_nav_window.py -q 全过，且至少断言：① navPoints == window.trading_days
2. ② window 五字段齐备且类型正确
3. ③ nav_coverage.verified 在场
4. ④ 构造含周末/节假日行的账户后 equity_curve 无这些行且 window.filtered_non_trading > 0
5. ⑤ nav_coverage 只反映净值序列自身缺口（构造基准缺口不影响它，落实 D-5）
6. ⑥ max_drawdown 取自 simulation_account 的重算值
7. ⑦ 既有响应键（returnsSource/sharpeRatio/annualVolatility/cumulativeReturn 等）一个不缺（回归）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-5 · 存量清理迁移与一致性校验（含备份与回滚）

**验收内容**：【存量清理迁移与一致性校验（含备份与回滚）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_migration_purge_nontrading_snapshots.py -q 全过，且至少断言：① dry-run 前后表行数与校验和一致（零副作用）
2. ② 只删 is_trading_day is false 的行，日历缺行(null)日期行不动
3. ③ 待删行数与实际不符时脚本非零退出并打印差异
4. ④ 备份行数 < 待删行数时中止
5. ⑤ --apply 后判据 SQL（非交易日净值行数）为 0
6. ⑥ 重算后 ./venv/bin/python tools/verify_equity_snapshot_consistency.py 逐账户 diff=0 且退出码 0
7. ⑦ 幂等：--apply 连跑两次，第二次删除 0 行且重算结果不变
8. ⑧ --rollback 恢复行数并打印“正在恢复 N 行非交易日净值行”的告警句。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-6 · 落常驻巡检判据并纠正失真的 is_synthetic 注释

**验收内容**：【落常驻巡检判据并纠正失真的 is_synthetic 注释】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_check_nontrading_equity_snapshots.py -q 全过，且至少断言：① 干净库下 ./venv/bin/python tools/check_nontrading_equity_snapshots.py 退出码 0
2. ② 插入一行非交易日净值行后退出码 2 且输出含该账户与日期
3. ③ 日历缺行的日期按 warn 单列、不计入违规（不误报）
4. ④ 检查器自身异常退出码 3
5. ⑤ grep -c is_synthetic application/services/trading_day_guard.py == 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-7 · 跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算

**验收内容**：【跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算】验收

**操作步骤**：
1. cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts 全过，且至少断言：① v2 返回 nav_coverage 时原样透出（含 basis 与 trading_day_source）
2. ② v2 缺字段时输出 verified=false 的“未做交易日校验”文案且不产生补跑建议
3. ③ 序列覆盖 2026-09-30→2026-10-08 时缺口为 0（国庆整段不算缺口）
4. ④ 缺 2026-09-25（真交易日）时仍报缺口（证明判据是活的）
5. ⑤ 该文件与 RiskMetricsTool.ts 内不再出现 getUTCDay 形式的交易日判定。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-9 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收 · 孤儿用例

**验收内容**：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——tests/test_daily_jobs_trading_day_gate.py、tests/test_equity_snapshot_daily_return.py、tests/test_equity_snapshot_trading_day_gate.py、tests/test_migration_purge_nontrading_snapshots.py、tests/test_nav_series.py、tests/test_trading_day_guard.py。请补 serves: 声明，或说明为何无需映射；通过时意见须写明处置方式。

**操作步骤**：
1. 孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——tests/test_daily_jobs_trading_day_gate.py、tests/test_equity_snapshot_daily_return.py、tests/test_equity_snapshot_trading_day_gate.py、tests/test_migration_purge_nontrading_snapshots.py、tests/test_nav_series.py、tests/test_trading_day_guard.py。请补 serves: 声明，或说明为何无需映射
2. 通过时意见须写明处置方式。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：通过

**验收状态**：✓ 通过

---

## 2. 测试报告

- v2 新增/改动 7 个测试文件：./venv/bin/python -m pytest tests/test_nav_series.py tests/test_equity_snapshot_trading_day_gate.py tests/test_equity_snapshot_daily_return.py tests/test_daily_jobs_trading_day_gate.py tests/test_risk_metrics_nav_window.py tests/test_migration_purge_nontrading_snapshots.py tests/test_check_nontrading_equity_snapshots.py -q → 117 passed, 1 skipped
- v2 邻域回归：./venv/bin/python -m pytest tests/api tests/migration/test_analysis_parity.py tests/test_api_smoke.py tests/services/evolution tests/test_multi_account_domain.py tests/application/test_account_trading_service_v2.py tests/services/test_risk_metrics_service.py tests/test_trading_day_guard.py -q → 391 passed, 1 skipped, 0 failed
- 巡检判据（生产实跑，只读）：PYTHONPATH=. ./venv/bin/python tools/check_nontrading_equity_snapshots.py → 违规 35 行 / 7 个日期（2026-08-08/08-15/08-29/09-05/09-06/09-12/10-02 各 5 行）→ [exit] 2（apply 前应有的红）
- 清理迁移（生产只读 dry-run）：PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py → [plan] 待删 35 行；[backup] 覆盖 35/35；[replay] 重算 65 行；[dry-run] 已 ROLLBACK 零改动；生产快照表 187 行未变、无 bak_* 表
- 一致性校验器（生产只读，apply 前基线）：./venv/bin/python tools/verify_equity_snapshot_consistency.py --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation → 差异 119 处 / 退出码 2（含库内 drawdown 为正的历史错值）
- 跨仓消费侧：cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts → 15 passed；相邻 tool-silent-failure-guard + account-default → 37 passed
- 测试证据（逐命令输出摘要 + 验收映射 + 变异验证 + 35 张卡的 covers 标注）：docs/requirements/REQ-261006190953-fc43/tests/test-evidence.md
- 复核报告（本轮抓到的 4 个真问题、逐 FR 核对、两项待人工放行、残余风险）：docs/requirements/REQ-261006190953-fc43/reviews/code-review.md
- 需求文档（含实施期裁定 D-6：删除谓词改白名单语义）：docs/requirements/REQ-261006190953-fc43/requirement.md
- 设计文档（data-model.md §3 已按 D-6 修订）：docs/requirements/REQ-261006190953-fc43/design/data-model.md
- 偏离与残余风险台账（DEV-1~DEV-15、R-1~R-7，逐条含证据与理由）：docs/requirements/REQ-261006190953-fc43/notes/implementation-deviations.md
- 待人工放行①：生产数据清理未执行（仅 dry-run）。命令：PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --apply；执行后巡检器应转 [exit] 0、校验器应转 diff=0
- 待人工放行②：v2 API 未重启，接口新字段 window/nav_coverage 尚未在 5001 生效（现场核对仍只有 5 个旧键）。重启会把其他需求在飞的未提交改动一并投上生产，属跨需求部署决定
- 已知红（非本需求造成）：tests/test_layer_purity.py 实测 320 > 基线 318。逐文件归因：本需求 +1（闸门设在仓储写入函数的结构性代价）、他人在飞 +1（should_have_run.py +3 / trading_day_resolver.py +2，同期清理 −4）；未调基线

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 落 nav_series 口径模块与契约（并留 shim 保导入兼容） | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:43 |
| v1-2 | 给净值仓储加唯一写入闸门，并让日收益基准按交易日回退 | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:43 |
| v1-3 | 接线两处写入入口：非交易日拒写并留痕 refused/skipped | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:43 |
| v1-4 | 读取端接线：days 改为交易日数并返回 window 与 nav_coverage | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:43 |
| v1-5 | 存量清理迁移与一致性校验（含备份与回滚） | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:43 |
| v1-6 | 落常驻巡检判据并纠正失真的 is_synthetic 注释 | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:45 |
| v1-7 | 跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算 | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:45 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:45 |
| v1-9 | 需求级验收 | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:45 |
| v1-10 | 需求级验收 · 孤儿用例 | ✓ 通过 | human/session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8 | 2026-10-06 20:45 |
