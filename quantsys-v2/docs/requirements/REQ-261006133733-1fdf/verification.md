# REQ-261006133733-1fdf 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：异常值检测从「恒报无异常」修成「真跑 + 三态可区分」。\n一行根因修复：成交量段迭代 polars DataFrame 改为 to_dicts() 列表。\n语义修复：三态返回 ok / has_anomalies(True|False|None) / unknown_reason，失败不再冒充「无异常」；数据不足与检测失败分开处置；两处消费点共用同一规则；审计修好 anomalies 键空转并新增未知 warning。\n实跑复验：报错 7995 → 0；质量分 95.01 → 86.28；问题股 748 → 4623；台账新增两键（0 / 402）。\n零 DDL / 零迁移 / 零开关。\n如实报出：① 中文日志需 JSON 扫描（grep 中文恒 0 属假绿）；② Z-score>3 使 81.3% 股票被判异常，质量门禁可用性下降，需另行裁定。\n独立复核发现并修正 1 处假绿（用例 T7/T9 数值不可区分），详见 reviews/code-review.md。

## 1. 验收列表

### v1-1 · 让异常检测真的运行，并输出可区分的三态

**验收内容**：【让异常检测真的运行，并输出可区分的三态】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q -k 'three_state or volume_anomaly or insufficient or detection_failure or score' → 全过
2. ② 真库探针：./venv/bin/python -c 「from application.services.data_quality_service import DataQualityService as D
3. print(D().validator.detect_anomalies('600519.SH','2026-07-01','2026-10-06'))」→ ok is True、error is None、total_anomalies 为真实计数（可 0）
4. ③ 失败注入：repo 抛错时 ok is False 且 has_anomalies is None（不得是 False），且不抛
5. ④ grep -rn has_anomalies application/services/data_validator.py 每处均为 is True / is False / is None / 字面赋值

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：真库探针 ok=True/has_anomalies=True/total_anomalies=1；三态 A/B/C 实测；质量分四态 94.0/74.0/92.5/74.0；数据质量链 37 passed / 1 skipped

**验收状态**：✓ 通过

---

### v1-2 · 下游按三态处置：失败不当干净、数据不足不扣分

**验收内容**：【下游按三态处置：失败不当干净、数据不足不扣分】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q -k 'consumer or summary or audit' → 全过
2. ② ./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q → 全过
3. ③ 三态汇总探针：对 3 只（正常/数据不足/失败）跑 check_quality_for_symbol 口径 → anomaly_unknown_count == 1 且 insufficient_history_count == 1
4. ④ 审计探针：注入失败 → warnings 含 anomaly_detection_unknown
5. 有异常 → 含 type='anomaly'（改前恒为空）
6. ⑤ 静态：grep -rn has_anomalies application/services/data_quality_service.py → 0 处真值判断

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：三态消费探针 counts=1/1，问题清单仅 ['C.SH']；审计 warnings 写 type=anomaly 与 type=anomaly_detection_unknown（改前恒为空）；护栏 17 passed

**验收状态**：✓ 通过

---

### v1-3 · 真 polars 回归锁与反例锁（先红后绿）

**验收内容**：【真 polars 回归锁与反例锁（先红后绿）】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q → 全过（≥15 条）
2. ② ./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q → 全过
3. ③ 反例锁记录：T3 在还原 t1 的一行改动后必须变红（前后各跑一次，输出进卡片汇报）
4. ④ 静态红线：grep -rn has_anomalies application/ adapters/ infrastructure/ | grep -v "is True\|is False\|is None\|'has_anomalies'\|has_anomalies=" → 空
5. ⑤ notify-guard 会话末 egress=0

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：新增 16 passed；反例锁 L1 实测 4 红后复原；静态锁 T15 注入即红；notify-guard egress=0

**验收状态**：✓ 通过

---

### v1-4 · 抽样实跑复验与读数对照留档

**验收内容**：【抽样实跑复验与读数对照留档】验收

**操作步骤**：
1. ① 观察文件存在且三节齐备（各带命令 + 原始输出摘要）：ls docs/requirements/REQ-261006133733-1fdf/notes/anomaly-recheck.md → 文件存在。② 抽样 ≥20 只：./venv/bin/python -c "from sqlalchemy import text
2. from application.services.data_quality_service import DataQualityService as D
3. s=D()
4. syms=[r[0] for r in s.kline_repo.session.execute(text(\"select symbol from quant.daily_klines where trade_date>='2026-07-01' group by symbol having count(*)>=60 order by symbol limit 20\")).fetchall()]
5. rows=[s.validator.detect_anomalies(x,'2026-07-01','2026-10-06') for x in syms]
6. print('okFalse=',sum(1 for r in rows if r['ok'] is False),'dist=',sorted(r['total_anomalies'] for r in rows))" → 期望 okFalse= 0。③ 同输出 dist 中出现 >0 的值。④ 报错归零（中文日志必须 JSON 扫描，grep 中文恒 0）：./venv/bin/python -c "import json
7. n=sum(1 for l in open('logs/api.log',encoding='utf-8',errors='replace') if l.strip().startswith('{') and '检测异常值失败' in str(json.loads(l).get('event','')) and str(json.loads(l).get('timestamp',''))>='2026-10-06T13:48')
8. print('新增=',n)" → 期望 新增= 0。⑤ 台账两新键已落：psql -h 127.0.0.1 -U mac -d quant_investment -At -c "select result->'details'->'details'->'check_summary'->>'anomaly_unknown_count', result->'details'->'details'->'check_summary'->>'insufficient_history_count' from quant.scheduler_runs where task_id=232 order by started_at desc limit 1" → 期望输出 0|402 形态的两值（键存在）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：抽样 okFalse= 0、19/20 有异常；run 3382 两新键落台账；报错 7995→0；score 95.01→86.28；issues 748→4623

**验收状态**：✓ 通过

---

### v1-5 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：需求级五项判定标准逐条绿：① 新增真 polars 用例 16 passed；② 与既有护栏合计 33 passed；③ 复现命令改前必错（TypeError 被吞）改后必对（ok=True/error=None）；④ 反例锁实测 4 红后复原；⑤ 抽样 okFalse=0 且 dist 出现>0。另有实跑整跑（run 3382）报错 7995→0

**验收状态**：✓ 通过

---

### v1-6 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：D-1（「继续」→ 下钻根因）：已兑现，traceback 存档于 requirement.md E3，并按需立项；D-2（范围 B）：已兑现——只做「一行修 + 吞错语义改造 + 回归锁 + 实跑复验」；同型扫描未做（仅登记后续线 1）、未改 get_daily_klines 返回类型、未改算法/阈值、未加开关或表列

**验收状态**：✓ 通过

---

## 2. 测试报告

- $ ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py tests/test_data_quality_job_guardrails.py -q → 33 passed（新增 16 + 既有护栏 17）
- 反例锁（红→绿）：把成交量段改回 for kline in klines → 4 条红；复原后 16 passed，shasum 一致、INJECT 残留 0
- 真库探针：detect_anomalies('600519.SH','2026-07-01','2026-10-06') → ok=True / has_anomalies=True / total_anomalies=1 / error=None
- 抽样 20 只（K 线 ≥60 行）→ okFalse= 0；19/20 报出异常；分布 [0,1,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,3,4,4]
- 整跑复验（用户批准重启 + 手动触发 task 232）：run 3382、success、13:48:51→13:54:22（331s）；check_summary 含 anomaly_unknown_count=0 / insufficient_history_count=402
- 读数对照（台账直读）：data_quality_score 95.01 → 86.28；stocks_with_issues 748 → 4623；两新键由不存在 → 落地
- 报错口径（JSON 扫描）：全部 7995 条（00:01–00:03 旧代码）；13:48 之后新增 0 条
- 静态红线：注入 if anomaly_info['has_anomalies']: → T15 立即红（锁可红）；复原后全绿
- 通知守卫：相关用例 egress=0 offenders=[]
- 测试证据（含 16 张卡 covers 标注）：docs/requirements/REQ-261006133733-1fdf/tests/test-evidence.md
- 独立复核报告：docs/requirements/REQ-261006133733-1fdf/reviews/code-review.md
- 复验留档：docs/requirements/REQ-261006133733-1fdf/notes/anomaly-recheck.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 让异常检测真的运行，并输出可区分的三态 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 13:57 |
| v1-2 | 下游按三态处置：失败不当干净、数据不足不扣分 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 13:57 |
| v1-3 | 真 polars 回归锁与反例锁（先红后绿） | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 13:57 |
| v1-4 | 抽样实跑复验与读数对照留档 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 13:57 |
| v1-5 | 需求级验收 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 13:57 |
| v1-6 | 需求级验收 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 13:58 |
