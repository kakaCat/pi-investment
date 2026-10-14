# t-b1dd5c 真 polars 回归锁与反例锁（先红后绿）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
真 polars 回归锁与反例锁（先红后绿）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
① ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q → 全过（≥15 条）；② ./venv/bin/python -m pytest tests/test_data_quality_job_guardrails.py -q → 全过；③ 反例锁记录：T3 在还原 t1 的一行改动后必须变红（前后各跑一次，输出进卡片汇报）；④ 静态红线：grep -rn has_anomalies application/ adapters/ infrastructure/ | grep -v "is True\|is False\|is None\|'has_anomalies'\|has_anomalies=" → 空；⑤ notify-guard 会话末 egress=0

## 实施方案（implementation）
新建 tests/test_data_validator_anomaly_detection.py，实现 design/test-cases.md 的 T1–T15：真 pl.DataFrame（≥40 行）正/负例、成交量异常直击（T3）、数据不足 B 态、失败 C 态、键集兼容、质量分四分态、两处消费点计数、审计 warnings、静态红线；并先在本卡开工前（改前）状态上跑一遍记录 L1–L4 的红（detect_anomalies 抛错被吞）。打桩点：用实例属性替换 validator.kline_repo / service.validator，KlineQualityRepository 用注入或实例替换。

## 上游产出摘要（dependsSummary）
- 让异常检测真的运行，并输出可区分的三态
- 下游按三态处置：失败不当干净、数据不足不扣分

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T05:47:01.373Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

t3 收尾：回归锁与反例锁交付，五项验收全绿，两次注入均能证红。

### 完成项

- 交付物：tests/test_data_validator_anomaly_detection.py（16 条，覆盖 design T1–T15 + 旧形兼容）
- 子卡链收口：研发 t-da0215 → 复核 t-97f26c → 测试 t-7463bd 三张全 done
- 父卡验收①：该文件 16 passed（≥15 条）
- 父卡验收②：与既有 tests/test_data_quality_job_guardrails.py 合计 33 passed
- 父卡验收③：反例锁实测——把成交量段改回错写法 → 4 条红（normal/price_anomaly/volume_anomaly/summary_counts），复原后全绿且 shasum 一致
- 父卡验收④：静态红线实测可红（注入 if ...['has_anomalies']: → 红），且不误伤 docstring 正文
- 父卡验收⑤：notify-guard intercepted=0 egress=0 offenders=[]
- 复核过程中修正一处我自己写出的假绿（T7/T9 覆盖率满分导致两条分支同值），改用 coverage_rate=90 后四态互不相同（94.0/74.0/92.5/74.0）

### 改动文件

- `tests/test_data_validator_anomaly_detection.py`

### 下一步

t4 抽样实跑复验与读数对照留档（≥20 只；日志归零；质量分/问题清单方向对照）。

---
