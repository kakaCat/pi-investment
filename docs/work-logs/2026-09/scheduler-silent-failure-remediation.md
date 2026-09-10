# 定时任务「静默空转」全链路修复（2026-09-10）

**责任人**：投资脑 investor / 窗口 w-23c70356
**触发**：用户提问「帮我检查定时任务还有类似的问题吗 执行时间0」——对 REQ-e5a251（K线静默失败）同类缺陷做全量排查
**范围确认**：用户选择「P0+P1 全修」+「允许修完立即补跑一次」
**仓库**：/Users/yunpeng/pi-investment（main），服务 quantsys-v2 :5001

---

## 一、结论速览

| 编号 | 缺陷 | 类型 | 影响 | 处置 |
|---|---|---|---|---|
| P0-A | market_perception_daily handler 调用了不存在的方法 MarketPerceptionService.regime_daily() | 必然 AttributeError 空转 | 2026-09-07~09-10 连续 4 个工作日 M1 快照任务完全空转 | 已修（改调真实入口 run_daily_snapshot，线程池执行） |
| P0-B | 调度器 run 状态只看「有没有抛异常」，handler 用返回值报错时不记录 | 静默成功（系统级） | 06-04 起 710 条 run 中 40 条静默失败；看门狗一路报 ok | 已修（统一 classify_job_result 判定，两条执行路径共用） |
| P0-C | run 的 started_at/completed_at/duration_ms 在 webhook 路径取「写库时刻」 | 执行时间失真（正是用户问的「执行时间0」） | 所有 Agent OS 委托任务的执行时间恒为 3~15ms，真实耗时（0.16s~3.3s）全部丢失 | 已修（如实回传真实起止时刻） |
| P1-A | 任务 325 market_style_update import 了从未存在的模块 infrastructure.scheduler.market_style_jobs | 死引用 | 该任务 4/4 失败 | 已修（改指真实实现 infrastructure/jobs/market_style_update_job.execute） |
| P1-B | infrastructure/jobs/kline_priority_sync.py SQL 引用不存在的列 daily_klines.updated_at | 埋雷（当前无调用方） | 一旦接线必报错 | 已修（改按 trade_date）+ 模块头标注未接线 |

**连带修复**：失败率看门狗 find_high_failure_tasks() 的聚合表达式非法（实测恒返回空列表），即使 4/4 失败也测不出来——这是 P0-B「静默成功」能长期潜伏的直接原因；已重写为 case() 显式计数，并把内层失败一并计入。

---

## 二、证据链（全部真实数据）

### P0-A：market_perception_daily 连败 4 天，run 全绿

    任务 323 market_perception_daily（工作日 15:30），数据源 quant.scheduler_runs（DB 查询，2026-09-10 23:4x）
      2026-09-07  failed(内层)  result: {"success": false, "error": "'MarketPerceptionService' object has no attribute 'regime_daily'"}
      2026-09-08  failed(内层)  同上
      2026-09-09  failed(内层)  run 3497  同上
      2026-09-10  failed(内层)  run 3521  同上
      —— 4 条 run 的 status 全部是 success（run 表），真实错误只躺在 result jsonb 里

真实入口：application/services/market_perception_service.py:64 run_daily_snapshot()（同步阻塞；返回 steps/stored/all_steps_success/failed_steps）。

### P0-C：执行时间列对 webhook 任务全部失真

    修复前  run 3533  market_style_update      duration_ms = 11   （同一 run 内层 elapsed_s = 0.16）
    修复前  run 3532  market_perception_daily  duration_ms = 13   （内层做了三步快照）
    根因    create_run()/complete_run() 内部用 now() 生成 started_at/completed_at；
            webhook 路径是「先跑完 handler 再写库」→ 两个时间戳都落在写库瞬间；
            _write_run_to_database 收下的 started_at/completed_at 是死参数（从未使用）。
    修复后  run 3534  market_style_update      duration_ms = 133，started 23:52:20.982 → completed 23:52:21.115，内层 elapsed_s = 0.13（一致）

> 附带修正前期审计的一处推理瑕疵：审计初期曾把「耗时 3~10ms」当作空转证据，
> 实际该列在本路径下无测量意义（恒为写库开销）。P0-A/P1-A 的结论仍成立——
> 依据是内层 result 的错误文本与数据表零写入，不是耗时。

### P0-B：静默成功 40 条 + 看门狗失效

    quant.scheduler_runs 全量（2026-06-04 起）：710 条 run，其中 40 条「行级 success + 内层 error」
    历史内层错误 Top：'KlineRepository' object has no attribute '_get_connection' ×6
                      regime_daily ×5 / NoneType…list_all_active ×5
                      '质量检查失败: name datetime is not defined' ×4 / QueuePool limit ×3
    看门狗（修复前）：find_high_failure_tasks(days=7, min_runs=3) → 空列表
                      —— 而任务 325 近 7 天 4/4 failed、323 4/4 failed
    修复前健康检查输出（09-09 / 09-10）：{"issues": [], "status": "ok", "high_failure": 0}

### 故障注入实测（不只测成功路径）

1. 把修复前的 webhook 模块（git show HEAD:./api/internal/scheduler_webhook.py 另存 /tmp/wh_old_w23c70356.py）单独加载，注入同一个失败 handler：
   OLD CODE run.status = success | error = None | result 内层 = {'success': False, 'error': "...regime_daily"}
   → 复现缺陷本体，同时证明新增用例在旧代码上必失败。
2. 新增测试 tests/test_scheduler_inner_failure.py（23 项，全绿），含：判定口径 16 组参数化；webhook 执行路径 4 例（内层失败 / status 风格 / 真成功 / 抛异常）；market_perception_daily 3 例（必须调 run_daily_snapshot、部分失败要暴露、端到端失败必须落 failed）。

### 修复后线上验证（真实触发，非模拟）

    [补跑] POST /internal/scheduler/webhook  job_type=market_perception_daily（用户已授权）
      run 3532  status=success  result: all_steps_success=true, failed_steps=null
        sentiment: stored=true coverage=5499 fear_greed=20.0
        regime   : stored=true regime=range  "情绪20, 量能0.68, 涨家占比17.1%, 指数5日-0.1%, close<MA20, MA20<MA60 → range"
        themes   : stored=true id=60 sector=电力 limit_up_count=5 fund_flow=4.48亿
      落库实证：quant.market_theme id=60 created_at=2026-09-10 23:50:33.409（= 本次补跑时刻，此前该行不存在）

    [验证 325] POST job_type=market_style_update
      run 3533  status=success  result: style=value scores={value 0.9321, growth 0.0679} updated=true source=sina_sector_spot coverage=0.898 elapsed_s=0.16
      （对比修复前 run 3520：failed "No module named 'infrastructure.scheduler.market_style_jobs'"）

    [看门狗] check_job_health(SchedulerRepository()) 实跑输出：
      summary = {total_enabled 25, zombie 1, missed 0, high_failure 2}
      issues  = zombie_running 每日数据质量检查(卡 1.9h, run 3527)
                high_failure_rate market_style_update 67% (4/6)
                high_failure_rate market_perception_daily 80% (4/5)

---

## 三、改动清单

| 文件 | 改动 |
|---|---|
| quantsys-v2/application/services/scheduler_handlers.py | P0-A：handler 改调 await asyncio.to_thread(service.run_daily_snapshot)，返回真实 steps/failed_steps/all_steps_success |
| quantsys-v2/api/internal/scheduler_webhook.py | P0-B：run 状态由内层结果判定（不再硬编码 success）；P0-C：真实起止时刻回传写库 |
| quantsys-v2/infrastructure/scheduler/job_executor.py | 新增模块级 classify_job_result()（统一两种 handler 约定），APScheduler 路径改用它 |
| quantsys-v2/adapters/outbound/repositories/scheduler_repository.py | 看门狗失败计数重写（case() + 内层失败）；create_run/complete_run 支持传入真实起止时刻 |
| quantsys-v2/infrastructure/scheduler/scheduler.py | P1-A：_handle_market_style_update 改 import 真实实现 |
| quantsys-v2/infrastructure/jobs/kline_priority_sync.py | P1-B：SQL 列名 updated_at → trade_date；模块头标注「当前无调用方」 |
| quantsys-v2/tests/test_scheduler_inner_failure.py | 新增 23 项回归（含故障注入） |

服务重启两次（PID 44984 → 47547）加载新代码；重启前已确认工作区所有 .py 文件 py_compile 通过。

---

## 四、遗留（未授权修改，仅记录）

1. **任务 232 每日数据质量检查**：成功耗时 9.7~116 分钟、失败 2.8 小时（InFailedSqlTransaction），且与进程内 data_quality 作业重复；09-10 22:00 起 run 3527 卡死 1.9h（看门狗已能报 zombie）。建议：拆分 / 加超时 / 去重。
2. **verification_job 早退语义**：无 5 日前调仓时返回裸 {"status": "completed"}（infrastructure/jobs/verification_job.py:354），建议改为 skipped: no 5-day-old rebalance，避免与「真跑过」混淆。
3. **看门狗告警会含历史失败**：本次修复后 7 日窗口内仍有 323/325 的历史失败记录，下次健康检查会报 high_failure=2，属预期残留，随窗口滑动自动消失。
4. 前期审计已登记的其他数据类待办（K线 001396 单行 volume ÷100、38 条 other 行、quant.stocks 缺近期新股等）不在本次范围。

---

**署名**：投资脑 investor / w-23c70356 · 2026-09-11 00:0x
