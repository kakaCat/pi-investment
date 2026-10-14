# t-7c5daa 落 nav_series 口径模块与契约（并留 shim 保导入兼容）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
落 nav_series 口径模块与契约（并留 shim 保导入兼容）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_nav_series.py -q 全过，且至少断言：① trading_day_set() 在日历表空/查询异常时返回 None（不是 set()）；② filter_trading_days(rows, None) 返回全量行；③ 传入含 09-05(六)/09-06(日) 行的序列后收益条数 = 交易日数 - 1；④ 跨节假日的涨跌归到复市首日那一段（09-30→10-08 只产出一条收益）；⑤ 覆盖 09-30→10-08 时 nav_coverage 的 missing_count == 0；⑥ 缺 2026-09-25（真交易日）时 missing_count == 1；⑦ trading_days=None 时 verified is False 且 missing_count == 0；⑧ from application.services.risk_metrics_service import nav_returns_from_snapshots 仍可导入且行为与 nav_series 一致。

## 实施方案（implementation）
新建 application/services/nav_series.py，导出四个函数（签名见 design/interfaces.md §2）：trading_day_set(exchange='ALL', force_refresh=False) 读 TradingCalendarORMRepository.list_trading_days 并做进程内 TTL 缓存，读失败/空表返回 None（绝不用空集表达失败）；filter_trading_days(rows, trading_days=None, date_of=...)，None 时原样返回；nav_returns_from_snapshots(snapshots, trading_days=None) 先丢 total_value<=0 行、再按交易日过滤、再相邻配对算收益，返回 (returns, points)；nav_coverage(snapshots, trading_days=None, max_listed=20) 返回 verified/points/from/to/missing_trading_days/missing_count/basis/trading_day_source。把 application/services/risk_metrics_service.py 里的 nav_returns_from_snapshots 改为转发 shim（保持既有导入路径可用，函数体与注释指向 nav_series）。新增 tests/test_nav_series.py。验证：./venv/bin/python -m pytest tests/test_nav_series.py -q 全过。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T11:43:37.800Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

卡 A 完工：净值序列口径收口到 nav_series 一处实现，未校验不过滤、不可得不当空集、缺口只算交易日；shim 保证既有导入路径不破

### 完成项

- 新建 application/services/nav_series.py（232 行）：交易日集合、行过滤、日收益、缺口计算
- 改 application/services/risk_metrics_service.py：同名函数改为兼容转发 shim（8 增 21 删）
- 新增 tests/test_nav_series.py（205 行，14 用例）覆盖验收 ①~⑧
- 子卡链四段全过：研发 → 联调 → 复核 → 测试，各段汇报已落卡文档
- 两处与设计的偏离已记账：notes/implementation-deviations.md（DEV-1 命名、DEV-2 来源取值）
- 完整验收入口 ./venv/bin/python -m pytest tests/test_nav_series.py -q → 14 passed

### 改动文件

- `application/services/nav_series.py`
- `application/services/risk_metrics_service.py`
- `tests/test_nav_series.py`
- `docs/requirements/REQ-261006190953-fc43/notes/implementation-deviations.md`

### 下一步

批 1 剩下卡 B：给净值仓储加唯一写入闸门并让日收益基准按交易日回退。它完成后 C/D/F/G 才可开工。

---
