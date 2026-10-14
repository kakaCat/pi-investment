# t-da502d 仓储层：complete_run_skipped + 抽 _finish_run

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
仓储层：complete_run_skipped + 抽 _finish_run

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_scheduler_run_result_json.py tests/test_scheduler_inner_failure.py -q 全过（既有 complete_run 调用方零回归）；新增单测断言 complete_run_skipped 后该行 status='skipped'、completed_at 非空、result 含 date/Decimal 也能落库、config.last_status='skipped'、last_error IS NULL。

## 实施方案（implementation）
修改 adapters/outbound/repositories/scheduler_repository.py：抽出私有 _finish_run(run_id, status, result=None, error=None, completed_at=None)，承载 completed_at / duration_ms / result 过 _json_safe / config.last_status / next_run_at 重算；complete_run 的签名与返回值逐字不变、内部改调 _finish_run(status=('success' if success else 'failed'))；新增 complete_run_skipped(run_id, result=None, completed_at=None) -> bool：写 status='skipped'、last_error=None、失败返回 False 绝不抛。列是 text NOT NULL DEFAULT 'running' 且无 CHECK，无需 DDL。

## 上游产出摘要（dependsSummary）
- 数据契约：三值列 + CHECK + 8 行回填 + ORM

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T01:58:31.152Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

t4 完成：仓储层具备 skipped 终态记账能力，三态收尾收口为一份实现，18 处调用方零改造。

### 完成项

- 抽出 _finish_run 作为 success / failed / skipped 三态共用收尾，complete_run 签名与行为逐字不变
- 新增 complete_run_skipped：last_error 恒 None、记账失败 rollback 后返回 False 绝不抛
- 新增 8 条单测（语义段假会话零 DB + 落库段一次真库往返，自建自删）
- 18 处既有 complete_run 调用方零改造；合并回归 75 passed 未降
- 登记一处既有近似重复（recover_orphan_runs 自写 duration_ms，事务形状不同，未强行合并）
- 四段子卡（研发/联调/复核/测试）均已汇报并关闭

### 改动文件

- `adapters/outbound/repositories/scheduler_repository.py`
- `tests/infrastructure/test_scheduler_run_skipped_ledger.py`

### 下一步

进入 t5（t-42eb9a）：执行期接门与跳过落账（含 manual 旁路）。

---
