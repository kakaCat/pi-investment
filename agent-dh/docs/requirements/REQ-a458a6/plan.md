# 实施计划（REQ-a458a6）

> 人批准时间：YYYY-MM-DD HH:mm（批准前本计划不构成拆分的许可）

**目标**：让模型训练只剩**一个可观测入口**，并让"该训却没训"在 24 小时内被发现——消除"真正训练的任务不可观测、可观测的任务被门控永久挡住"的错位。

**做法**：保留 in-app 的 `ModelTrainDailyJob`（task 320，有 `quant.scheduler_runs` 台账/watchdog），撤掉系统 crontab 里两条**不可观测**的训练条目；把门控从"floor 天数 > 7"（等价满 8 天、且与 7 天节律自我抵消）改成"实际秒数 ≥ 6.5 天"（日检查下节律稳定落在第 7 天，见执行记录推演表）；再补一道模型新鲜度巡检（in-app + 外部 launchd 各一处，避免与它要监测的调度同生共死）。

**全局约束**：
- 只动物业已存在的组件，不新增训练实现；唯一真实训练器仍是 `application/services/scheduler_tasks.handle_model_train_auto`。
- 不改交易宪法、不改 regime 仓位、不涉及账户与下单。
- 所有判定必须用**真实数据**（`quant.ml_models``train_date`/`test_accuracy`）并留痕（runs 的 result.reason 可复核）。
- 回滚必须是"加回两行 crontab / git revert"，不得出现只能靠改数据库才能回退的改动。

## 任务表

| key | 任务 | phase | side | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| t1 | 修正训练门控语义（秒级阈值 + 缺失兜底 + 文案） | implement | backend | - | 单测覆盖 5.9/6.0/7.0/8.0 天与 train_date 缺失；手动 trigger task 320，runs 里 reason 带一位小数与阈值 |
| t2 | 调度去重：撤两条训练 crontab，训练只留 task 320 | implement | backend | t1 | `crontab -l` 不再含 `0 3 * * 1`、`0 3 1 * *`；连续 ≥2 个训练周期里训练均由 task 320 在本机 runs 中留下记录 |
| t3 | 模型新鲜度巡检（in-app freshness_guard + 外部 launchd 检查） | implement | backend | - | 把 `quant.ml_models` 里最新 lightgbm 的 train_date 人为改老 11 天 → 两处各告警一次，复原后不再告警 |
| t4 | 删除死代码 `application/services/ml_train_task.py` | implement | backend | - | `grep -rn ml_train_task` 只剩文档注记；全量导入/冒烟测试通过 |
| t5 | 跳过通知降噪（skipped 不单独推飞书） | implement | backend | t1 | 造一次 skipped 无飞书；造一次 success 有飞书；skipped 仍完整落在 runs |
| t6 | 验收：故障注入 + 一个训练周期观察 | test | backend | t1,t2,t3,t4,t5 | 见"验收方式"；观测窗口内模型年龄峰值 ≤8 天 |
| t7 | 修复基准巡检的滞后比较失效（执行期并入，用户两问确认） | implement | backend | - | 正常跑 exit 0 且无 stderr 重定向报错；把比较改坏后必须 `FAIL: 巡检自检未通过` 并投错误事件 |

## 任务细节

### t1 修正训练门控语义
- Files：Modify `quantsys-v2/application/services/scheduler_tasks.py`（`_check_train_needed`，:1453-1489）；Modify `quantsys-v2/application/jobs/model_jobs.py`（docstring 口径）；Test `quantsys-v2/tests/test_model_train_gate.py`（新建）
- 现状（已核实）：`days_old = (now - train_date).days` 向下取整 + 判定 `> 7` ⇒ 实际"满 8 天才算过期"。实证：09-13 03:30 那条 `age=7d` 的跳过，模型真实年龄 7.69 天；周一 03:00 训练出来的模型在下周一 03:00 复查只有 6 天 23h59m → 必然跳过（cron 自己也被挡）。
- 改法：
  1. 常量 `RETRAIN_MIN_AGE_DAYS = 6.5`（周节律 7 天 + 半天抖动余量），判定经纯函数 `_age_needs_retrain(age_days)`；
  2. `train_date` 缺失 → `return (True, "模型缺 train_date 元数据，按需重训")`（消除 :1489 的 UnboundLocalError）；
  3. reason 文案带一位小数与阈值：`f"模型{version}仍有效（age={age_days:.1f}d < {RETRAIN_MIN_AGE_DAYS}d, acc={test_acc:.4f}）"`；
  4. 删掉 :202 注释里"且数据有更新"半句（代码无此判断，避免二次误导）。
- 验收：`pytest quantsys-v2/tests/test_model_train_gate.py -q`；`scheduler_manage trigger task_id=320` 后读 `quant.scheduler_runs` 的 result.reason。

### t2 调度去重
- Files：Modify crontab（`crontab -l` → 去掉两行）；Modify `agent-dh/docs/...` 或 quantsys-v2 运维文档，写明"训练唯一入口 = task 320；需要强制训练时手工跑 `quantsys-v2/tools/cron_train_model_force.sh`"
- 现状（已核实）：真正训练的是 crontab `0 3 * * 1`（周一 03:00，`/tmp/model-train-YYYYMMDD.log`）与 `0 3 1 * *`（每月 1 号强制）；两者**不进** `quant.scheduler_runs`、无告警、日志留在 /tmp（系统会清理——08-24/08-31 的日志已不可得，无法判断当时是没跑还是跑失败）。09-01 强制训练的产物至今未落库、无人审。
- 为什么删 cron 而不是删 task 320：删掉 task 320 后，剩下的 cron 仍受同一门控（t1 修好后每 7 天可训）但**不可观测**；而 task 320 的每次运行都进 runs、受 scheduler-watchdog 覆盖，且可手动 trigger。
- 保留 `0 10 * * *` 性能监控（`cron_monitor_model_performance.sh`），本次不动。
- 回滚：把两行加回 crontab（脚本仍在 `quantsys-v2/tools/`）。
- 验收：`crontab -l`；一个训练周期后 `select * from quant.scheduler_runs where task_id=320` 出现 `status=success, version=...`。

### t3 模型新鲜度巡检
- Files（执行时调整，理由见文末「执行记录」）：Modify `quantsys-v2/application/jobs/model_jobs.py`（`ModelTrainDailyJob.execute` 训练后复核 + `_model_freshness_alerts`）；Create `/Users/yunpeng/pi-investment/scripts/model-freshness-check.sh` + `~/Library/LaunchAgents/com.pi-investment.model-freshness-check.plist`（每日 09:05，独立于 v2 进程内调度）
- 判定：最新 lightgbm 模型 `(now - train_date) > 10 天` 或 `test_accuracy < 0.55` → 告警（in-app 走 `_send_feishu`，外部走既有"投递 open 错误事件"通道）。
- 为什么两处都放：in-app 巡检与它要监测的调度**同生共死**（调度宿主挂了巡检也挂），外部 launchd 是唯一能在"in-app 全挂"时说话的那条线。
- 验收：人工把 `quant.ml_models` 里最新 lightgbm 的 train_date 改老 11 天 → 两处各告警一次；复原。

### t4 删除死代码
- Files：Delete `quantsys-v2/application/services/ml_train_task.py`（4 个函数：`handle_model_train_auto`/`_check_train_needed`/`_try_switch_model`/`register_model_train_task`，grep 零调用方）
- 理由：它与 `scheduler_tasks` 的同名实现重复，且**保留着 2026-09-05 已修掉的 tz-naive/aware 相减崩溃**（:200 `datetime.now() - train_date`），是同一个坑的第二次踩坑面；09-05 工作日志已记"建议删除防误导"。
- 验收：`grep -rn ml_train_task` 只剩文档注记；`python -c "import adapters.inbound.fastapi_app.main"` 与既有冒烟测试通过。

### t5 跳过通知降噪
- Files：Modify `quantsys-v2/application/services/scheduler_tasks.py`（skipped 分支的 `send_ml_train_notification`，:1159-1163）；如需保留可见性则改走每日汇总
- 现状：`_format_train_content`（`feishu_formatters.py:435`）对 skipped 输出"**跳过原因**: ..."，t1 修好后日任务每周仍有 6 天是 skipped。
- 改法：skipped 不单独推送（runs 里已有完整 result）；success/failed 保持即时推送。
- 验收：造一次 skipped（`scheduler_manage trigger`）确认无飞书；造一次 success 确认有飞书。

### t6 验收
- 故障注入：①把最新模型 train_date 改老 11 天 → t3 两处告警；②把 task 320 临时 disable 一天 → 恢复后仍能按门控训练；③清空 `train_date` 字段 → t1 不再抛异常且给出明确 reason（测完复原）。
- 周期观察：≥1 个训练周期内 `select max(started_at), status from quant.scheduler_runs where task_id=320` 出现 success+version；模型年龄峰值 ≤8 天。
- 回归：`quant.ml_models` 新增行的 `test_accuracy` 与模型目录 `training_report_*.json` 一致。

## 明确不在本次范围（避免夹带）
1. 孤儿产物对账/归档（8 个 pkl 无 DB 记录、2 条 DB 记录无文件）—— R-020 数据卫生，单独走；根因（`create(dict)` 静默吞）已于 2026-09-05 commit `85a9b1e2` 修复，属历史残留。
2. "每月强制训练 + 人工审核"的审核闭环 —— 随 t2 撤销该 cron；若要恢复该能力，须连审核队列（待审记录 + 对比卡片）一起做，另立需求。
3. xgboost 早期试验产物的清理。

## 风险与回滚
- t2 若只撤 cron 不做 t1 ⇒ 复训周期静默从 ~8 天变 14 天（本计划把 t2 依赖 t1，禁止单独执行）。
- t4 删除文件属可逆操作（git revert）；t3 的告警若阈值过紧会变噪声，暂定 10 天，观测一周后按需调整。

## 执行记录（2026-09-14，w-4db568de）

| 任务 | 状态 | 证据 |
|---|---|---|
| t1 门控语义 | ✅ 已生效 | `RETRAIN_MIN_AGE_DAYS=6.5` + `_model_age_days` + `_age_needs_retrain`；11 条回归测试全过（含节律测试，`tests/test_model_train_gate.py`）；线上 trigger task 320 → runs 3709 reason `仍有效 (age=0.0d < 6.5d, acc=0.5975)` |
| t2 调度去重 | ⚠️ 部分 | 两个 cron 脚本已改为「不训练 / 需显式确认」（行为上训练只剩 task 320）；**crontab 行本身改不动**——macOS TCC 拒写 `/var/at/tmp`（`crontab: tmp/tmp.1646: Operation not permitted`），须人工删行（命令见下方「待人工收尾」） |
| t3 新鲜度巡检 | ✅ 双线 | in-app：Job 每次运行后复核（runs 3707 含 `freshness_alerts: []`）；外部：launchd 每日 09:05，故障注入实测 `FAIL 模型年龄 11.04 天 > 10 天` + `error-event ingest HTTP=201` |
| t4 死代码 | ✅ | `application/services/ml_train_task.py` 已删（零调用方，含同款 tz 崩溃实现） |
| t5 通知降噪 | ✅ | skipped 分支不再推送；线上 trigger 后 `notification_logs` 计数未变（320→320） |
| t6 验收 | 🔶 注入已过、周期观察待满 | 四条故障注入全过（见下）；「≥1 个 7 天训练周期的观察」需等到 09-21/09-22 才能判 |
| t7 基准巡检比较 | ✅ | 正常跑 exit 0、stderr 干净；故障注入（`lag()`→`echo 0`）→ 自检 FAIL + `error-event ingest HTTP=201` + exit 1 |

**注入结果**（脚本 `/tmp/inject_model_freshness.py`，跑完自动精确复原，DB 已核对复原）：
1. 全部 lightgbm 行整体前移 11 天 → 外部巡检 FAIL + 事件入库 201；`_model_freshness_alerts()` → `fatal=True`；门控 → `(True, 模型已11.0天未更新（阈值6.5天）)`；Job 端到端 → `success=False`，高优通知经 Agent OS alerts 渠道投递成功。
   （第一次注入只前移最新一行 → 次新行顶上来当「最新」，外部巡检照样 OK，脚本报的是 0905 的 8.71 天 —— 注入必须整体前移。）
2. train_date 置空 → `(True, 模型…缺 train_date 元数据，按需重训)`，**不再抛 UnboundLocalError**。
3. 复原后复核：门控 `(False, 仍有效 (age=0.0d < 6.5d, acc=0.5975))`、外部巡检 OK。

**执行期偏差（3 处，均已核实理由）**：
- **t3 落点改了**：原计划改 `daily_jobs_bootstrap._job_freshness_guard`，但该文件此刻有**其他窗口的在途改动**（`git status` 显示 M），配套的 `tests/test_freshness_guard.py` 也被人改着；为不踩踏，把 in-app 检查放到职责更贴的 `application/jobs/model_jobs.py`（干净文件）。
- **外部线新建而非复用**：`benchmark-freshness-check.sh` 头部明写「本脚本与对应 launchd 任务保留不动」，故另建 `model-freshness-check.sh` + 独立 plist，复用同一错误事件通道。
- **t2 用脚本兜底**：crontab 不可改（TCC），改为让两个 cron 脚本拒绝训练（weekly 直接 no-op、force 需 `CONFIRM_FORCE_TRAIN=1`），使「训练唯一入口」在行为上成立，等人工删行收尾。

**待人工收尾（一条命令）**：
```bash
crontab -l | grep -v cron_train_model.sh | grep -v cron_train_model_force.sh | crontab -
```


**阈值修订记录（同日 04:01，w-4db568de）**：首版取 6.0 天，依据是「每周 cron 检查一次」——但 t2 之后唯一的入口是**日检查**（03:30），节律随之改变。按时间轴推演（`_age_needs_retrain` + 03:30 日检查）：

| 阈值 | 训练于 03:00:11 | 训练于 03:30:11 |
|---|---|---|
| 6.0 | 6.02 天（偏早） | 7.00 天 |
| **6.5** | **7.02 天** | **7.00 天** |
| 7.0 | 7.02 天 | 8.00 天（偏晚、每次漂一天） |

故改为 **6.5**：两种训练时点都稳定落在第 7 天；漏跑一天仍能在次日补上。已加 `test_daily_cadence_is_seven_days_for_both_training_times` 把这个性质钉住（阈值若再被改动而破坏节律，测试会红）。线上复核：runs 3709 reason `仍有效 (age=0.0d < 6.5d, acc=0.5975)`。

### t7 修复基准巡检的滞后比较失效（并入说明）
- 来源：执行 t1-t6 时顺带读到该脚本与日志，发现它的「新鲜度」一项从未生效：`[ "$BENCH_LAST" < "$REF_LAST" ]` 在 bash 单括号里是**输入重定向**（stderr 可见 `line 37: 2026-09-11: No such file or directory`），比较不成立、FAIL 永远为空 → 基准滞后也报 OK（实证 09-13 08:40 日志：基准 2026-09-10 vs 市场 2026-09-11 仍输出 OK —— 正是本巡检要抓的「归因/相对收益失真」场景）。
- 并入理由：本窗口已被 reqboard 绑定在 REQ-a458a6（`reqboard_create` 返回 `REQBOARD_WINDOW_BOUND`，第二个需求立不了项）；该缺陷与本次治理属**同一族**（巡检/门控「绿灯其实是坏的」静默失效），且已经用户两问确认（名称「修复 benchmark-freshness-check.sh 的基准滞后比较失效」、类型 bug）。
- 改法：滞后比较交给 python3（`lag()`：ISO 串字典序），并新增**每次运行都跑的自检**（`lag(旧,新)` 必须给出 1/0）；自检不通过时同样投错误事件，防止巡检再次退化成「永远 OK」。顺带把参照标的提成 `${REF:-600519}` 便于人工换参照。
- 验收：正常跑 `exit 0` + `[benchmark-check] OK: 000300.SH 最新=2026-09-11（市场最新=2026-09-11）`、stderr 无重定向报错；故障注入（把 `lag()` 换成 `echo 0`）→ `FAIL: 巡检自检未通过：滞后比较失效（lag(旧,新) 应为 1/0，实得 00）` + `error-event ingest HTTP=201` + `exit 1`（已在 /tmp 副本实测）。

