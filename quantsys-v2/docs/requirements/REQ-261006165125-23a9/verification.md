# REQ-261006165125-23a9 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付：每日任务通知改为「有事才说」——新增判据模块 notify_policy（无事 = no_output is True 或 status ∈ {no_event, no_op}），命中时开始与完成两条飞书都不发；开始消息改为超阈值（默认 60s）「仍在运行」提示；失败/异常一律照发且不受判据影响；人工触发必有回执；台账语义零变更；两个 env 开关可一键回滚。六张卡全过，合并口径 152 passed、notify-guard egress=0，服务已重启部署（新 PID 57853，17:09:55 宿主线程起，状态端点 200）。

未取证项（如实标注，不宣称完成）：真实排班里「无事时飞书静默」需要一次新代码下的自然排班，部署时点（17:09）已过当日 16:45，故该判定留待 2026-10-07 16:45，判定命令与口径见 notes/rollback-and-observation.md §3.2。

三处设计/计划自身的错误已发现并登记于 reviews/review-report.md §3：① 设计漏判 test_daily_jobs_trading_day_gate.py 的两条旧口径断言（已修）；② 验收端点 today 不存在（404，真实为 status）；③ 进程级开关复跑因夹具 delenv 而得到「假回滚绿」，回滚证据改由用例内 setenv + 进程级 python -c 承担。

## 1. 验收列表

### v1-1 · 新建通知判据模块 notify_policy（无事判据 + env 解析）

**验收内容**：【新建通知判据模块 notify_policy（无事判据 + env 解析）】验收

**操作步骤**：
1. 四条命令退出码全 0：① ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p
2. assert p.is_no_op({'status':'no_event'}) and p.is_no_op({'status':' NO_OP '}) and p.is_no_op({'no_output':True})
3. assert not p.is_no_op({'no_output':1}) and not p.is_no_op({'status':'success'}) and not p.is_no_op(None) and not p.is_no_op('x')
4. assert p.should_send_completion(result={'status':'no_event'}) is False
5. assert p.should_send_completion(result={'status':'no_event'}, manual=True) is True
6. print('policy ok')"
7. ② DAILY_JOBS_RUNNING_NOTICE_SECONDS=abc … assert p.running_notice_seconds()==60.0
8. ③ DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 … assert p.running_notice_seconds()==0.0
9. ④ DAILY_JOBS_NOTIFY_NOOP=1 … assert p.notify_noop_enabled() and p.should_send_start()。另：! grep -nE '^(from|import) (application|domain|infrastructure)' 该文件 → 无命中（层边界只许向内）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：四条验收命令全过：is_no_op 11 组断言（含 no_output=1 反例）；running_notice_seconds 坏值/0/30 三态；开关态；层边界 grep 无 application/domain/infrastructure 命中

**验收状态**：✓ 通过

---

### v1-2 · alerting 抽出完成消息组装 format_completion

**验收内容**：【alerting 抽出完成消息组装 format_completion】验收

**操作步骤**：
1. ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import alerting as a
2. t=a.format_completion('event_calendar_check','desc',1.2,{'updated':1})
3. assert t.startswith('✅ 每日任务完成：event_calendar_check') and '耗时: 1.2 秒' in t, t
4. assert a.format_completion('j','d',1.2,{'updated':1},manual=True).startswith('✅ 每日任务完成（人工触发）：j')
5. assert a.format_completion('j','d',1.2,{'no_output':True},warn_no_output=True).startswith('⚠️ 每日任务完成（无有效产出）：j')
6. print('format ok')" → 打印 format ok。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：python -c 打印 format ok：标题三级优先级（人工触发 > 无有效产出 > ✅）与正文（描述/耗时/摘要）实测通过；未改 _send_feishu 等四个既有符号

**验收状态**：✓ 通过

---

### v1-3 · runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job

**验收内容**：【runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py tests/test_false_success_guard.py tests/test_notify_guard.py -q → 全过（跳过/失败路径未被误伤）
2. ② ./venv/bin/python -c "from datetime import time as dtime
3. from adapters.inbound.fastapi_app.daily_jobs import runtime
4. from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef
5. sent=[]
6. runtime._send_feishu=lambda t:(sent.append(t),True)[1]
7. runtime._mark_running=lambda *a,**k:None
8. runtime._mark_done=lambda *a,**k:None
9. mk=lambda r: JobDef('event_calendar_check',dtime(16,45),(0,1,2,3,4,5,6),lambda:r,'事件日历检查')
10. runtime._run_job(mk({'status':'no_event'}),'2026-10-07')
11. assert sent==[], sent
12. runtime._run_job(mk({'updated':1}),'2026-10-07')
13. assert len(sent)==1 and sent[0].startswith('✅'), sent
14. print('host ok')" → 打印 host ok
15. ③ grep -n 'manual: bool = False' runtime.py 与 grep -n 'inprocess_job_notify_skipped' runtime.py 各有命中。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：既有 4 文件 75 passed；桩 runtime._send_feishu 实跑四态（no_event→0、{'updated':1}→1、抛异常→1 🚨、无事+内层失败→🚨）；grep 命中 manual 参数/notify_skipped/kwargs manual=True

**验收状态**：✓ 通过

---

### v1-4 · 新增 tests/test_daily_jobs_quiet_noop.py（T-1~T-16 回归锁）

**验收内容**：【新增 tests/test_daily_jobs_quiet_noop.py（T-1~T-16 回归锁）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q → 全过（≥16 passed）
2. 并用 2>&1 | tail -3 确认 notify-guard 会话末打印 egress=0、offenders=[]（未声明的真实外发会让用例失败）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q → 40 passed；T-1~T-16 编号齐备、无 T-17+；三条反向锁在位；打桩点检查无 alerting/bootstrap 上的桩；egress=0

**验收状态**：✓ 通过

---

### v1-5 · 改写被新口径推翻的 2 条既有断言 + 相邻回归

**验收内容**：【改写被新口径推翻的 2 条既有断言 + 相邻回归】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py tests/test_notify_guard.py -q → 全过
2. ② grep -n "startswith('⚠️ 每日任务完成" tests/test_daily_jobs_notify_truthfulness.py → 仅 1 处，且该用例先 setenv('DAILY_JOBS_NOTIFY_NOOP','true')（旧断言不得在默认态残留）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py tests/test_notify_guard.py -q → 30 passed；旧断言仅剩开关态 1 处且该用例先 setenv；另修同类旧断言 2 条（trading_day_gate，2 条→1 条完成）

**验收状态**：✓ 通过

---

### v1-6 · 回滚态验证 + 部署重启 + 真实观察留痕

**验收内容**：【回滚态验证 + 部署重启 + 真实观察留痕】验收

**操作步骤**：
1. ① DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q → 全过
2. ② DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p
3. assert p.running_notice_seconds()==0.0" → 退出码 0
4. ③ launchctl kickstart -k gui/501/com.pi-investment.v2-api && sleep 8 && curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/jobs/inprocess/today → 200
5. ④ psql -d quant_investment -Atc "select job_id,status,result->>'status' from quant.inprocess_job_runs where run_date=current_date and job_id='event_calendar_check'
6. " → success|no_event（窗口未到则在 notes 里标注待观察）
7. notes 文件含上述四项结论。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：回滚：switch-mode OK / notice-off OK（进程级显式 env）；部署：PID 57853、17:09:55 宿主线程起、/api/jobs/inprocess/status → 200；台账 event_calendar_check|success|no_event；真实排班静默标为待观察（2026-10-07 16:45）

**验收状态**：✓ 通过

---

### v1-7 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：合并口径 8 文件 152 passed / egress=0；服务已按本仓库代码重启部署；两处偏差登记（端点 today 404 → status 200；夹具 delenv 使进程级开关复跑不构成回滚证据）；唯一未取证项=真实排班静默，判定命令已固化待执行

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：D-1（立项：feature/expert）：文档落 docs/requirements/REQ-261006165125-23a9/，五份设计 + 六张卡全部实施完成。D-2（原话「没有事情不应该发送飞书信息」）：兑现为 should_send_completion 默认对 is_no_op 返回 False，实测 no_event 与 no_output 两种无事均 0 条消息（T-6/T-11），台账仍 success。D-3（原话「A. 通用规则 + 两条都不发（含开始）」）：兑现为①通用判据模块 notify_policy（非单任务补丁，任何任务按 result 键命中即静默）、②开始消息改为条件式 + 超阈值提示（默认 60s，T-12~T-14）、③失败与异常仍必发（T-8/T-9）

**验收状态**：✓ 通过

---

## 2. 测试报告

- ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py tests/test_daily_jobs_notify_truthfulness.py tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py tests/test_false_success_guard.py tests/test_notify_guard.py tests/test_freshness_guard.py tests/test_job_failure_alerting.py -q → 152 passed, 1 warning in 7.39s；notify-guard intercepted=0 egress=0 offenders=[]
- ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q → 40 passed（T-1~T-16 参数化）
- 裁定对照：docs/requirements/REQ-261006165125-23a9/requirement.md D-1/D-2/D-3 三行；兑现证据见 results 的 decision-compare 项
- 宿主四态实测：no_event→0 条（并记 inprocess_job_notify_skipped）、{'updated':1}→1 条 ✅、manual=True→1 条（人工触发）、handler 抛异常→1 条 🚨
- 回滚①：DAILY_JOBS_NOTIFY_NOOP=true python -c → switch-mode OK（无事也发）；回滚②：DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 → notice-off OK
- 部署：plutil -p 确认 plist 指向本仓库；launchctl kickstart -k 后 PID 57853；logs/api.log 2026-10-06T17:09:55 daily-jobs host thread started（9 个任务含 event_calendar_check）
- curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5001/api/jobs/inprocess/status → 200
- psql -d quant_investment -Atc "select job_id,status,result->>'status' from quant.inprocess_job_runs where run_date=current_date and job_id='event_calendar_check'" → event_calendar_check|success|no_event
- 测试证据（含 covers 覆盖度标注与逐卡索引）：docs/requirements/REQ-261006165125-23a9/tests/test-evidence.md
- 评审报告：docs/requirements/REQ-261006165125-23a9/reviews/review-report.md（含 3 处设计/计划自身错误的发现与处置）
- 回滚与观察留痕：docs/requirements/REQ-261006165125-23a9/notes/rollback-and-observation.md（§3.2 次日判定命令、§5 测试段复跑记录）
- 待观察（如实标注，不宣称完成）：2026-10-07 16:45 自然排班后按 notes §3.2 三条判定（台账 success|no_event、grep inprocess_job_notify_skipped、飞书侧无该任务两条）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 新建通知判据模块 notify_policy（无事判据 + env 解析） | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-2 | alerting 抽出完成消息组装 format_completion | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-3 | runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-4 | 新增 tests/test_daily_jobs_quiet_noop.py（T-1~T-16 回归锁） | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-5 | 改写被新口径推翻的 2 条既有断言 + 相邻回归 | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-6 | 回滚态验证 + 部署重启 + 真实观察留痕 | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-7 | 需求级验收 | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-981b7858-34a5-4ea0-88c9-a7e2efb95886 | 2026-10-06 17:14 |
