# t-baed9f 服务层返回 per_symbol 全量事实并修 original_count 取键

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
服务层返回 per_symbol 全量事实并修 original_count 取键

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① set(res.keys()) ⊇ {'summary','stocks_with_issues','per_symbol'} 且 per_symbol['600519'] 恰含设计规定的 8 键；② 小样本跑完写库后 select original_count from public.kline_data_quality order by created_at desc limit 1 的结果 > 0；③ ./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q 全过。

## 实施方案（implementation）
改 application/services/data_quality_service.py：① check_data_quality 循环内把每只标的的 coverage_rate / missing_days_count / quality_score / overall_score / grade / has_duplicates / has_anomalies / anomaly_unknown 收进 per_symbol（唯一一次 _calculate_grade 调用），返回体新增 per_symbol 键（形状照设计 data-model 文档 §6）；② _persist_quality_audit 的 original_count 改取 gap_info.get('total_trading_days', 0)，grade/overall_score 改为接收循环内算好的值不再重算；③ summary 既有键一个不改。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T08:51:44.428Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

t3 完成：服务层交出全量逐标的事实、评级单点计算、审计列取对键。

### 完成项

- check_data_quality 新增 per_symbol（全量 5686 条、8 键），实测 600519 键集与设计一致
- grade/overall_score 改为循环内单点计算，审计写入与告警统计同源（实测逐项相等）
- original_count 改取 total_trading_days：实测 0 → 60（窗口交易日数）
- 4 张子卡（研发/联调/复核/测试）全部完成；既有 17 条护栏用例全过

### 改动文件

- `application/services/data_quality_service.py`

### 下一步

t4 接线（作业层）已消费本卡的 per_symbol

---
