# 独立复核报告 · REQ-261006093620-a315（库表调度补交易日门）

**复核者**：独立复核窗口（不是提交者）
**复核时间**：2026-10-06 10:12–10:20 CST（本机 `date` → `Tue Oct  6 10:1x CST 2026`）
**工作区**：`/Users/mac/Documents/ai/pi-investment/quantsys-v2`（monorepo 根 `/Users/mac/Documents/ai/pi-investment`）
**方法**：所有判定均来自我自己读代码或跑命令，**未复用提交者的自述**；除本文件外未写入任何文件；未调用任何 `reqboard_*` 工具。

---

## 1. 结论

**6 条断言全部成立，但其中 3 条带边界条件；另发现 8 处偏离/风险，其中 4 处提交者材料未登记。**

一句话：机制本身是对的、真库与生产读数都站得住；**交付形态与"降级留痕"两处比材料声称的弱**。

| # | 断言 | 判定 | 一句话依据 |
|---|---|---|---|
| 1 | `should_skip` 三值语义 + fail-open + 永不抛 | **成立** | 真值表 7 场景 + 14 组脏输入实跑，无一次抛出；未知策略 warning+fail-open |
| 2 | 落点顺序 / 不执行 / 不通知 / `last_error` 空 | **成立**（2 条衍生缺口） | 并发中存在 running 仍写 skipped（我自造用例）；生产 run 3381 `error=NULL`、10:00–10:15 零通知 |
| 3 | `manual` 旁路 + 一次性 job + 不扰动 cron 排期 | **成立** | 假门在 manual 下**根本没被问**；生产代码已无 `modify_job`；测试断言 `next_run_time` 不变且通过 |
| 4 | `complete_run_skipped` 写 skipped 且绝不抛；`complete_run` 签名/行为不变 | **成立** | 签名逐字不变（16 个调用点零破坏）；`_finish_run` 抽取是**逐字搬运**；真库往返 + 生产双证 |
| 5 | `gate.py` 纯转发壳；桩在新模块且证伪用例有效 | **成立**（别名形态可绕过） | 壳只暴露 4 个转发名、`hasattr(g,'TradingDayGuard') is False`；我用变异模拟验证②会红 |
| 6 | 两套状态集；missed 仍告警；watchdog 只改 v2 那处 | **成立**（watchdog 无生产效果） | 纯函数实测：skipped 槽位 ok/不入漏跑；无留痕仍 missed 且 `dedup_keys` 非空 |

生产侧我只做了**只读**读数，未写生产库；所有写操作都是测试库里的既有/自建自删用例。

---

## 2. 逐条核实

### 断言 1 · 判据语义（`application/services/trading_day_gate.py`）

**我跑了什么**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
# ① 四组必跑测试之一
./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q
# ② 我自己写的脏输入/真值表探测（写到 /tmp，跑完已删）
./venv/bin/python - <<'EOF'   # 真守卫 + 7 组时间点 + 5 组脏策略 + 3 组脏 now
...
EOF
# ③ 生产交付的一次性差分脚本
./venv/bin/python docs/requirements/REQ-261006093620-a315/notes/gate-differential-check.py
```

**看到什么**

```
tests/test_scheduler_trading_day_gate.py ..................... [100%]
21 passed, 1 warning in 1.17s
notify-guard intercepted=0 egress=0 offenders=[]

真实守门·法定节假日(10-06)   policy='trading-days' skip=True  src='trading-calendar-holiday'
真实守门·周末(10-03)         policy='trading-days' skip=True  src='weekend'
#232 分档·周末(10-03)        policy='holidays'     skip=False src='weekend'          ← 周末照跑 ✓
#232 分档·法定节假日(10-06)  policy='holidays'     skip=True  src='trading-calendar-holiday'
真实守门·交易日(09-30)       policy='trading-days' skip=False src='trading-calendar'
未知策略 'HOLIDAYS'/None/''/123/object() → 全部 skip=False + warning（fail-open，不抛）
now=脏字符串 / now=object()  → skip=False src='compute-error' degraded=True（不抛）
```

**判定：成立。** 三值语义与文档一致；「只跳法定节假日、周末照跑」这条在**真日历**上验过（不是靠桩）；未知策略与脏 `now` 均 fail-open 且不抛。

**两条边界**（见 F4）：`should_skip('trading-days', <未来日>)` → `skip=True / source='future'`；`policy=None` 会走"未知策略"分支打 warning（模块 docstring 把"缺省"与"未知"并列，措辞与实际分支不完全一致）。

### 断言 2 · 落点正确性（`infrastructure/scheduler/job_executor.py`）

**我跑了什么**

```bash
sed -n '175,300p' infrastructure/scheduler/job_executor.py       # 读顺序
./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py \
    tests/infrastructure/test_scheduler_run_skipped_ledger.py -q
# 我自造的落点用例：带「已存在 running run」的假仓储，验证门是否真在并发检查之前
./venv/bin/python /tmp/rev_a315_probe.py     # 已删
# 真库 e2e 探针（真仓储+真门+测试库）
./venv/bin/python -m pytest docs/requirements/REQ-261006093620-a315/notes/test_e2e_holiday_skip_probe.py -q -s
# 生产只读
psql -d quant_investment -c "select id,task_id,status,started_at,error,result->>'trading_day_source' src from quant.scheduler_runs where started_at::date='2026-10-06' order by id desc limit 5;"
psql -d quant_investment -c "select id,name,last_status,last_error,next_run_at from quant.scheduler_tasks where id in (250,261);"
```

**看到什么**

```
L236 is_enabled → return ；L247 交易日门 → L269 并发检查 → L292 create_run     ← 顺序（读码）
[A 无 running run]     skipped=1 executed=[] completed=[]
[A 有 running run]     skipped=1 executed=[] completed=[]   ← 门确实在并发检查之前（否则提前 return，skipped=0）
14 passed in 0.68s

[e2e] run.status = skipped / run.error = None
[e2e] result = {'skipped': True, 'trading_day_source': 'trading-calendar-holiday', 'degraded': False, 'policy': 'trading-days', ...}

 id  | task_id | status  |          started_at           | error |           src
 3381|   261   | skipped | 2026-10-06 10:10:00.072629+08 |       | trading-calendar-holiday
 3380|   259   | success | 2026-10-06 09:40:00.256317+08 |       |
 3379|   250   | success | 2026-10-06 09:25:16.780830+08 |       |      ← 改前那次（原始问题）
 261 | chan-scan-daily | last_status=skipped | last_error=(空) | next_run_at=2026-10-07 10:10:00+08
agent_os.notification_logs（10:00–10:15）：0 rows                                   ← 不打扰 ✓
```

**判定：成立。** 顺序、零执行、零通知、`error` 为空，四条我各自独立取到证据（读码 + 自造用例 + 真库 e2e + 生产台账）。

**两条衍生缺口**（不是本断言要求，但属同一代码路径）：见 **F5**（降级照跑分支不留痕）与 **F6**（跳过分支 `create_run` 失败会外抛）。

### 断言 3 · 人工旁路（`manual` / `trigger_task_now`）

**我跑了什么**

```bash
sed -n '455,500p' infrastructure/scheduler/apscheduler_service.py       # trigger_task_now
sed -n '415,470p' adapters/inbound/fastapi_app/routes/scheduler_async.py # 路由
grep -rn "modify_job" --include='*.py' . | grep -v /venv/                  # 是否还有旧写法
./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q
# 我自造：manual=True + 假门返回「跳过」→ 断言门"根本没被问"
./venv/bin/python /tmp/rev_a315_probe.py
```

**看到什么**

```
trigger_task_now: self.scheduler.add_job(func=execute_scheduled_job,
    trigger=DateTrigger(run_date=datetime.now()), args=[task_id],
    kwargs={'manual': True}, id=f'manual_{task_id}_{int(_time.time())}',
    replace_existing=False, misfire_grace_time=None)          ← 无 modify_job
modify_job 全仓（排除 venv）：仅命中 apscheduler_service.py 的**注释**（说明为何不再用）
13 passed in 0.66s
[manual=True] 门调用记录 = []   ← 门未被询问（tests/infrastructure/test_scheduler_skip_ledger.py::test_manual_trigger_runs_on_holiday 同断言）
```

**判定：成立。** 「不再 `modify_job`」由**全仓零生产引用**证明（强于文档自述）；「不扰动 cron 排期」由既有测试断言 `after.next_run_time == next_before` 且通过；`manual=True` 时门确实不被询问。

### 断言 4 · 台账三态（`scheduler_repository`）

**我跑了什么**

```bash
grep -rn "\.complete_run(" --include='*.py' . | grep -v /venv/ | grep -v complete_run_skipped   # 数调用方
git diff quantsys-v2/adapters/outbound/repositories/scheduler_repository.py                     # 抽取是否等价
sed -n '140,189p' tests/infrastructure/test_scheduler_run_skipped_ledger.py                      # 真库往返
grep -n "_safe_rollback" -A 12 adapters/outbound/repositories/scheduler_repository.py            # 是否吞异常
```

**看到什么**

```
complete_run 调用点 = 16（生产 10：scheduler.py×6、job_executor.py×3、scheduler_webhook.py×1；测试 6）
complete_run_skipped 生产调用点 = 1（job_executor.py:254）
签名：complete_run(run_id, success=True, result=None, error=None, completed_at=None)  ← 与 HEAD 逐字相同
diff：旧函数体**整段搬进** _finish_run，complete_run 变为「try: return self._finish_run(...) except: rollback+raise」
      → 与原 try/except 语义相同；未增删任何收尾步骤
def _safe_rollback(self):  try: self.session.rollback()  except Exception as e: logger.warning(...)   ← 自身也吞
真库往返用例（test_skipped_status_persists_in_real_db）：status='skipped' / completed_at 非空 /
      error is None / result.skipped is True / last_status='skipped' / last_error is None，自建自删
```

**判定：成立。** 签名与行为确实没变（搬运式重构，我逐段比对了 diff）；`skipped` 落账与 `last_error=NULL` 有真库往返与生产两条独立证据；"绝不抛"成立（唯一的 except 分支调用 `_safe_rollback`，它自己吞异常）。

### 断言 5 · 打桩点迁移（`daily_jobs/gate.py` + 其测试）

**我跑了什么**

```bash
./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import gate as g;
    print(hasattr(g,'TradingDayGuard'), g.__all__, [n for n in vars(g) if not n.startswith('_')])"
grep -rn "daily_jobs.gate import" --include='*.py' . | grep -v /venv/
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q
# 变异模拟：构造「判定被复制回壳里」的版本，看证伪用例②是否真的会红（/tmp 脚本，已删）
./venv/bin/python /tmp/rev_a315_tripwire.py
```

**看到什么**

```
has TradingDayGuard: False
__all__ = ['SOURCE_GATE_ERROR','is_non_trading_day','skip_non_trading_day','verdict_info']
public  = ['SOURCE_GATE_ERROR','annotations','is_non_trading_day','skip_non_trading_day','verdict_info']
导入方：runtime.py（skip_non_trading_day）、pipeline.py（is_non_trading_day）→ 均在 __all__ 内 ✓
28 passed（本文件）／65 passed（含 should_have_run 31 + orm_drift 6）

变异模拟输出：
现状壳 + 桩打新模块(节假日): (True, {...'trading-calendar-holiday'})
现状壳 + 桩打新模块(交易日): (False, {...'trading-calendar'})      ← ① 随桩变，锁成立
本地实现 + 测试①的桩(新模块): (False, {...'trading-calendar'})      ← ① 会红
本地实现 + 测试②的桩(壳): 抛 RuntimeError('boom')                 ← ② 会红 = 证伪用例有效
```

**判定：成立。** 壳确为纯转发（无本地实现、无 `TradingDayGuard` 属性、导入方所需名字齐备）；证伪用例**双向都有效**——我构造的"复制回壳里"变异会让 ① 与 ② 都红。
**边界**：若复制回去时**用别名**（`from ... import TradingDayGuard as G`），① ② 都会**静默通过**（因为 ① 用真守卫在 10-06 恰好也判节假日跳过，② 打的是壳上未被读取的名字）。属窄口，见 F7。

### 断言 6 · 巡检口径（`should_have_run` + 根 `scripts/scheduler_watchdog.py`）

**我跑了什么**

```bash
grep -n "skipped\|HANDLED_STATUSES\|REAL_RUN_STATUSES" application/services/should_have_run.py
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_should_have_run.py \
    tests/test_orm_db_drift.py -q
# 我用纯函数直接喂四组输入（不经 DB）
./venv/bin/python /tmp/rev_a315_probe.py
git diff scripts/scheduler_watchdog.py
grep -rn "scheduler_watchdog" --include='*.py' --include='*.sh' --include='*.plist' .   # 谁在调它
grep -n "should_have_run\|audit_should_have_run" tools/health_probe.py ; cat ~/Library/LaunchAgents/com.pi-investment.health-probe.plist
```

**看到什么**

```
L257 HANDLED_STATUSES = ('success','failed','skipped')      ← 算"已处理"
L260 REAL_RUN_STATUSES = ('success','failed')               ← 不算"真执行"

[a 该槽位有 skipped 留痕] verdict=ok     计入漏跑=0  reason=该排班已被交易日门按日历跳过…不算漏跑
[b 无任何留痕]            verdict=missed 计入漏跑=1  reason=scheduler_runs 中无任何执行留痕
[c 该槽位有 success]      verdict=ok     计入漏跑=0  last_run_status='success'
[d skipped 但早于应跑时刻] verdict=missed 计入漏跑=1  reason=最近一次留痕是交易日门跳过（@…），早于应跑时刻…
告警面：skipped 槽位 dedup_keys=[] ；无留痕 dedup_keys=['pre-market-scan@2026-10-07T09:25:00+08:00']
65 passed in 1.34s

git diff scripts/scheduler_watchdog.py：**单一 hunk**，只把 v2 段 status='success' → IN ('success','skipped')，
   并留警示注释「下方 os:missed 段查 Agent OS 的 public.task_runs…不要一并改」→ Agent OS 那处未动 ✓
谁在调 watchdog：仅 `scripts/tests/test_scheduler_watchdog_catchup.py` 与一条 docstring 引用；launchd 无该项
health_probe：把判据委托给 should_have_run.audit_should_have_run，且由
   ~/Library/LaunchAgents/com.pi-investment.health-probe.plist（跑 tools/health_probe.py）承载 → **这条才是活的**
```

**判定：成立。** 两套集合的分工与我实测的三态完全一致（skipped 算已处理、不算真执行，missed 仍告警）；watchdog 只改了 v2 那处、Agent OS 那处保持原样。
**附带事实**：`scheduler_watchdog.py` **没有任何调度器在调用它**（无 launchd、无脚本引用），所以 t7 对它的改动**当前不产生生产效果**；真正防误报的是 `health_probe → should_have_run`（这条链是活的）。

---

## 3. 我发现的偏离、风险或可疑之处

### F1（高·未登记）7 个交付物在 git 里**未跟踪**，其中包含判据核心与迁移

```bash
git status --porcelain -- <file>
?? quantsys-v2/application/services/trading_day_gate.py          ← 判据唯一真源
?? quantsys-v2/application/services/should_have_run.py           ← t7 口径同步
?? quantsys-v2/adapters/inbound/fastapi_app/daily_jobs/gate.py   ← 转发壳
?? quantsys-v2/infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py
?? quantsys-v2/tests/test_scheduler_trading_day_gate.py
?? quantsys-v2/tests/infrastructure/test_scheduler_skip_ledger.py
?? quantsys-v2/tests/infrastructure/test_scheduler_run_skipped_ledger.py
 M quantsys-v2/infrastructure/scheduler/job_executor.py          ← 只有 4 个文件是"修改"
 M .../scheduler_repository.py   M .../orm/models/scheduler.py   M .../apscheduler_service.py
git ls-files --error-unmatch quantsys-v2/application/services/should_have_run.py
→ error: pathspec … did not match any file(s) known to git
```

两个后果，都不是风格问题：
1. **复核被削弱**：t7 声称把「`status != 'missed'` 一套」改成「两套集合」——但该文件在 HEAD 里**根本不存在**（未跟踪），**没有基线可 diff**，我无法核实"改了什么"，只能核实"现状对不对"（现状对）。
2. **交付不可复现**：一次 `git clean -fd`（或换机克隆）会丢掉判据模块、转发壳、迁移与三份新测试 —— 而 `job_executor.py`（已跟踪）仍在 `from application.services.trading_day_gate import ...`，即**留下一个 import 悬空的已跟踪文件**。

`verification.md` §7 列了 8 条"已知限制"，**没有这一条**。注：`daily_jobs/gate.py`、`should_have_run.py` 的未跟踪状态是更早需求（2b8c / a7cd）留下的，但本次把**判据核心**也放进了同一形态，等于把风险放大了一个量级。

### F2（中·未登记）`GET /api/scheduler/runs/failed` 会把 `skipped` 当"失败"返回

```bash
grep -n "statuses = \['failed'" adapters/inbound/fastapi_app/routes/scheduler_async.py
520:    statuses = ['failed', 'missed', 'skipped']
521:    failed = _scheduler.list_runs(..., statuses=statuses, ...)
git diff --stat quantsys-v2/adapters/inbound/fastapi_app/routes/scheduler_async.py   # 空 = 本次未改该文件
```

`design/data-model.md` §5 的消费者矩阵把接口层记成「`list_runs` / `get_scheduler_task_runs` → **透传 status** → 无需改」，这与实际不符：这个端点不是透传，而是**按状态筛选**，且筛选集**已含 `skipped`**。后果：休市日起每天最多 8 条正常的"门跳过"会出现在名为 `/runs/failed` 的列表里。前端把 `skipped` 映射成「跳过」，所以不是显示崩溃，属**口径污染**——而"把非 success 当异常"的口径同步正是 FR-3 ④ 的承诺范围。该行代码**早于本次改动**（`git diff` 为空），因此是**审计缺口**而非本次引入的回归；但需求自称做了"逐个对账"，这一处漏了。

### F3（中·未登记）`verification.md` 仍把**已失效**的差分脚本当等价性证据

同一需求的两份文档口径相反：

- `notes/gate-differential-check.py` 头部（提交者自己写的）：
  > ⚠️ **一次性产物 —— t3 之后本脚本失效**：`old_gate` 与 `new_gate` 指向**同一个函数对象**——再跑它只是自比，**不再构成等价性证据**。
- `notes/acceptance-run.md:224-226` 也如实登记了这一点。
- 但 `verification.md:39` 仍写：**FR-2 …「差分核对 7 场景 × 3 入口与旧实现逐字相同」** ← 作为 FR-2 的落地证据，**无任何附注**。

我实跑该脚本，输出确实"全部一致、退出码 0"（7 场景 × 3 入口），但结论是**同义反复**：两个名字 now 指向同一实现。建议：verification.md 该行补一句"该证据仅对 t1 当时的两实现并存有效，t3 后为自比"，或直接删掉这半句。

### F4（低·潜在）`trading-days` 对**未来日期**判 `skip=True`（`source='future'`）

```
真实守门·未来日(10-08)   policy='trading-days' skip=True  src='future' degraded=False
真实守门·未来日(10-07)   policy='trading-days' skip=True  src='future' degraded=False   ← 今天 10-06，"明天"也是 future
```

生产不可达（门喂的是 `datetime.now()`），所以**不是活缺陷**。但两条要注意：① 模块 docstring 承诺「本模块判的是当天……**永不**把未来日期喂给守卫」——这是**约定而非不变量**，代码里没有任何断言/防护；② 差分脚本把"未来日期 → skip=True"列为**期望**，说明"future 即跳过"是被固化的行为。若将来有人拿这个判据去做"补跑该不该跑"（补跑天然面向过去→未来窗口），会得到反直觉的"跳过"。

### F5（中·未登记）**FR-2 的"降级不许静默"只落实了一半**

我自造用例：假门返回 `(skip=False, {'source':'unavailable','degraded':True,...})`（即"日历链不可用 → 照跑"）：

```
[降级→照跑] 落账 = [{'success': True, 'result': {'status':'success','note':'命令自己的返回'}, 'error': None}]
[节假日→跳过] 落账 = [{'skipped': {'reason':'日历链不可用 → 按降级照跑', 'trading_day_source':'unavailable','degraded':True,...}}]
```

即：**跳过分支**把 `degraded`/`trading_day_source`/`policy` 五键带进 run 的 result（✓）；**照跑分支**（含降级照跑）**什么都不带**——`gate_info` 在 `if skip:` 之外从未被使用。对照 ③ DailyJobs 有 `test_degraded_run_annotates_result_and_warns`（降级会注入 result 并告警），② 这条路径比 ③ 弱。

需要公正地说：守卫层自己会打 `trading_calendar_not_covering` / `weekday_fallback` 之类的 warning（我在测试库 e2e 就看到了 `trading_calendar_not_covering anchor=2026-10-06 calendar_max=None`），所以**不是全静默**；但这些日志**不带 task_id**，无法回答"10-07 哪些任务因为降级而没被门拦住"。需求 FR-2 的原话是「把 source / degraded 带进 run 的 result **与日志**（不许静默）」→ 照跑分支未达标。

### F6（低·未登记）跳过分支的异常隔离只做了一半

```
*** 抛到了调用方（调度线程）：RuntimeError: DB 挂了：写 run 失败
    completed=[]   ← 异常处理器里那次 complete_run 没执行
```

外层 `try`（L225）只配了 `finally`（L379），**没有 except**；内层 `try/except`（L300/357）只覆盖 step 5–6。因此跳过分支里 `repo.create_run()` 失败会**原样抛进 APScheduler 线程**、且**不留任何 run 记录**。FR-3 的"记账失败不许影响调度"只对 `complete_run_skipped` 成立（它确实吞），对同分支的第一次写库不成立。无测试覆盖。严重度低（要在读 `get_task` 成功之后、写 run 那一刻 DB 刚好挂才触发），但它与 FR-3 的措辞有落差。

### F7（低）证伪用例的覆盖边界：**别名形态会绕过**

我用变异模拟验证了②对"用模块全局名复制回壳里"的形态**有效**（会红）。但若复制回去时用别名导入（`from ... import TradingDayGuard as G` 再在壳内实现），则 ①（用真守卫在 10-06 恰好也判节假日跳过）与 ②（打的 `TradingDayGuard` 名字不被读取）**都会通过**。属窄口，登记备查。

### F8（信息）"新增取值 skipped"的措辞会夸大

```
psql -c "select status,count(*),min(started_at)::date,max(started_at)::date from quant.scheduler_runs group by 1"
 success | 3000 | 2026-06-04 | 2026-10-06
 failed  |  155 | 2026-06-04 | 2026-10-02
 skipped |    1 | 2026-10-06 | 2026-10-06     ← 唯一一条就是本次 10:10 的
 cancelled|   1 | 2026-06-06 | 2026-06-06
```

对**表**而言"新增取值"准确（此前无 skipped 行，且 `status` 列无 CHECK，'cancelled' 这种值早就存在）。但仓库里 `application/observability/run_outcome.py:107` **早已定义** `STATUS_SKIPPED`（V13 链用），所以"本仓首次引入 skipped 语义"是不成立的。设计文档若往那个方向表述会夸大，现文档（`data-model.md` §5）只说"台账契约新增 `skipped`"，是准确的，**无需改**，此处仅备查。

---

## 4. 未能验证的事项

| # | 事项 | 原因 |
|---|---|---|
| U1 | t7 改动的**前后差异**（`should_have_run` 从"一套 `status != 'missed'`"改成"两套集合"） | 该文件**未跟踪**（F1），HEAD 里不存在，无基线可 diff。我只能核实**现状**满足三态语义 |
| U2 | `2026-10-07`（休市）/ `2026-10-08`（复市首日）的真实台账 | 未来日期，库里不存在。10-08 的"应判交易日"我只验到 `resolve_trading_day(date(2026,10,8)).date == date(2026,10,8) → True`（日历表覆盖到 2026-12-31），未验"真实复市日不跳" |
| U3 | `scripts/scheduler_watchdog.py` 自带测试 | 本机 venv 缺 `croniter`（我核实：`import croniter → ModuleNotFoundError`），其 10 条用例跑不了；我只能读 diff + 读代码。提交者 §7.4 的这条自述**属实** |
| U4 | 客户/展示端的完整链路 | 我只核到 `web-frontend/src/types/scheduler.ts` 的 `RunLevel` 已含 `'skipped'`、`mappers.ts` 会映射为 skipped；未起前端验证渲染 |
| U5 | APScheduler 持久化 jobstore 里一次性 manual job 的"执行后自动摘除" | 未在生产验证（需真触发一次人工触发）；我只读了代码与既有测试对 `next_run_time` 不变的断言 |

---

## 5. 复核范围与时间戳

- **复核范围**：`application/services/trading_day_gate.py`、`application/services/should_have_run.py`、`application/observability/run_outcome.py`、`infrastructure/scheduler/{job_executor,apscheduler_service}.py`、`adapters/outbound/repositories/scheduler_repository.py`、`adapters/inbound/fastapi_app/daily_jobs/{gate,runtime,pipeline,alerting}.py`、`adapters/inbound/fastapi_app/routes/scheduler_async.py`、`infrastructure/persistence/orm/models/scheduler.py`、`infrastructure/persistence/migrations/20261006_*.py`、`tests/{test_scheduler_trading_day_gate,test_daily_jobs_trading_day_gate,test_should_have_run,test_orm_db_drift}.py`、`tests/infrastructure/{test_scheduler_skip_ledger,test_scheduler_run_skipped_ledger,test_apscheduler_service}.py`、`docs/requirements/REQ-261006093620-a315/{requirement.md,verification.md,design/data-model.md,notes/*}`、monorepo 根 `scripts/scheduler_watchdog.py`。
- **跑过的命令**：题面指定的 5 条全部跑过（4 条 pytest 共 113 通过、差分脚本退出码 0），另加 2 条 notes 内 e2e 探针（2 passed）、5 条生产/测试库只读 SQL、4 个自写临时探测脚本（已删除：`/tmp/rev_a315_{probe,tripwire,unbound,degraded}.py`）。
- **未触碰**：未修改任何源码/测试/文档（除本文件）；未写生产库；未调用任何 `reqboard_*` 工具；未推进任何任务/需求状态。
- **本文件**：`docs/requirements/REQ-261006093620-a315/reviews/code-review.md`（新建，父目录由本次创建）。
- **复核时间**：2026-10-06 10:12–10:20 CST。
