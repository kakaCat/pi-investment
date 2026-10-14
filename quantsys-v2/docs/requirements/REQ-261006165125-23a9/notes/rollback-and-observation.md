# 回滚与真实观察留痕 · REQ-261006165125-23a9

**记录时间**: 2026-10-06 17:09（部署完成时点）
**对应任务卡**: `rollback`（t-f9a549）
**结论一句话**: 两条回滚路径**可执行且已实测**；本特性的真实排班观察窗口在**次日 16:45**，
当次（10-06 16:45）是**部署前**的旧行为，故如实标注为"待观察"，不以推断代替实测。

## 1. 回滚路径验证（进程级显式 env，非 pytest 夹具）

```bash
# ① 开关打开 = 恢复旧行为（无事也发：开始 + 完成）
DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -c "
from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p
assert p.notify_noop_enabled() is True and p.should_send_start() is True
assert p.should_send_completion(result={'status':'no_event'}) is True"
#   → 回滚态①通过：无事也发（开始+完成）

# ② 只关超阈值提示，其余口径不变
DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 ./venv/bin/python -c "
from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p
assert p.running_notice_seconds()==0.0
assert p.should_send_completion(result={'updated':1}) is True"
#   → 回滚态②通过：提示关闭、其余不变

# ③ 代码级回滚面：git revert 本次提交（无 schema、无数据迁移）
```

### ⚠️ 证据口径陷阱（必须记住，否则会得到"假绿"）

回归测试的 `sent` 夹具里有 `monkeypatch.delenv('DAILY_JOBS_NOTIFY_NOOP', raising=False)`，
**这是刻意的环境隔离**——它让宿主环境变量不能污染用例。副作用是：

```bash
# ❌ 这不是回滚验证：夹具会把环境变量删掉，跑出来仍是默认态
DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q
#   → 40 passed，但它证明的是"用例与环境隔离"，不是"开关能恢复旧行为"

# ✅ 回滚证据由这两处承担：
#   a. 用例内显式 setenv：T-4（开关解析）、T-11（开关态旧行为：开始+完成、零产出 ⚠️）
#   b. 上面的进程级 python -c（① ②）
```

## 2. 部署（本仓库代码 + launchd）

```bash
# 服务跑的确实是本仓库（实查 plist）
plutil -p ~/Library/LaunchAgents/com.pi-investment.v2-api.plist \
  | grep -A4 -E "ProgramArguments|WorkingDirectory"
#   → ProgramArguments[0] = /Users/mac/.../quantsys-v2/venv/bin/python
#     ProgramArguments[2] = /Users/mac/.../quantsys-v2/adapters/inbound/fastapi_app/main.py
#     WorkingDirectory     = /Users/mac/.../quantsys-v2

launchctl kickstart -k gui/501/com.pi-investment.v2-api && sleep 12
#   → 新进程 PID 57853（旧 99249 已被 -k 终止）
#   → logs/api.log：2026-10-06T17:09:55 "✅ daily-jobs host thread started"
#      jobs 清单含 event_calendar_check（9 个任务齐备）

# 服务健康（真实端点）
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/jobs/inprocess/status
#   → 200；响应体 {"success": true, "data": {"jobs": [ {job_id, status, scheduled_at, ...}, ... ]}}
```

**计划偏差（如实记录）**：拆分计划与需求文档里给的验收命令写的是
`http://127.0.0.1:5001/api/jobs/inprocess/today` —— 该路径**不存在**，实测 **404**。
真实路由是 `/api/jobs/inprocess/status`（`routes/daily_jobs_async.py:14`，另有
`POST /api/jobs/inprocess/{job_id}/run`）。后续验收按**更正后**的路径执行。

## 3. 真实观察（待观察 → 次日 16:45 判定）

### 3.1 当次事实

| 项 | 值 | 说明 |
|---|---|---|
| 2026-10-06 16:45:18 `event_calendar_check` | `success` / `result.status=no_event` | **部署前**的运行，走的是旧口径 |
| 当日飞书 | 实发 2 条（▶️ 开始 + ✅ 完成） | 这正是用户投诉的那两条，属旧行为 |

**部署时点（17:09）已过当日 16:45**，故本次改动**没有**当日的排班样本可用——
这一点不掩饰：当次运行不能作为"新口径生效"的证据。

### 3.2 次日判定口径（可直接复制执行）

```bash
# ① 台账仍留痕（无事也 success，result 原样）
psql -d quant_investment -Atc "select job_id,status,result->>'status'
  from quant.inprocess_job_runs where run_date='2026-10-07' and job_id='event_calendar_check';"
#   期望：event_calendar_check|success|no_event

# ② 静默原因可查（新增可观测点）
grep inprocess_job_notify_skipped logs/api.log | tail -5
#   期望：{"job":"event_calendar_check","reason":"no_op","manual":false,...}

# ③ 飞书侧（人看）：当日无「▶️ 每日任务开始：event_calendar_check」与
#    「✅ 每日任务完成：event_calendar_check」两条（对照 10-06 的 2 条）
```

**判定未完成前，本需求不得宣称"用户可见的噪音已消除"**——只能说"代码与回归锁已就位、
部署已验证、真实排班观察待 2026-10-07 16:45"。

## 4. 回滚决策树（真出问题时按序执行）

1. 若"该发的消息没发"且确认是判据过宽 → `DAILY_JOBS_NOTIFY_NOOP=true` 恢复旧行为（改 plist
   `EnvironmentVariables` 后 `launchctl kickstart -k`），再回滚代码；
2. 若只是"仍在运行"提示太吵 → `DAILY_JOBS_RUNNING_NOTICE_SECONDS=0`（不动代码）；
3. 若出现漏发失败告警 → 这是本设计明确不允许的（失败路径不经判据）：立即 `git revert`，
   并把现场（`quant.inprocess_job_runs` 行 + `logs/api.log` 片段）附到需求评论。

## 5. 测试段复跑记录（2026-10-06 17:12:07，按**更正后**的命令）

| # | 命令（要点） | 实测输出 |
|---|---|---|
| ① | `DAILY_JOBS_NOTIFY_NOOP=true python -c …` | `switch-mode OK`（开关态：开始发、无事也发完成） |
| ② | `DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 python -c …` | `notice-off OK`（阈值 0 = 关闭提示） |
| ③ | `curl …/api/jobs/inprocess/status` | `status_api=200`；`launchctl list` → 57853（宿主进程在跑） |
| ④ | `psql … where run_date=current_date and job_id='event_calendar_check'` | `event_calendar_check\|success\|no_event` |
| ④b | `grep -c inprocess_job_notify_skipped logs/api.log` | **0** —— 与预期一致：当日 16:45 那次运行发生在**部署前**（旧代码），新日志事件要到次日排班才会出现 |
| ⑤ | 合并口径 8 个测试文件 | **152 passed**，`notify-guard … egress=0 offenders=[]` |

**判定**：回滚可用性（①②）、部署有效性（③④）、代码正确性（⑤）三项**已有实测证据**；
唯一未取证的是「真实排班里无事时飞书真的静默」——它需要一次**新代码下的自然排班**（2026-10-07 16:45），
故本卡以「待观察」收尾，并在需求验收材料中如实标注，不宣称已完成用户可见效果。
