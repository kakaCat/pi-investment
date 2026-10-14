# t-17fce0 空转读数：EvolutionFitnessORMRepository 两个只读聚合方法

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
空转读数：EvolutionFitnessORMRepository 两个只读聚合方法

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/repositories/test_evolution_fitness_repository.py -q 全过；新增断言：插 3 个 window_end（ok 条数分别 2/0/1）时返回顺序与计数为倒序正确；最新一条为 insufficient_sample、次新为 ok 时 get_last_ok_window_end() 返回次新的 window_end；全部非 ok 时返回 None。

## 实施方案（implementation）
adapters/outbound/repositories/evolution_fitness_repository.py：新增 list_recent_window_ok_counts(limit=20, window_days=20) -> List[Tuple[date,int]] —— group_by(window_end) + count(case((status 等于 ok,1)))，按 window_end 倒序、按 limit 截断；新增 get_last_ok_window_end(window_days=20) -> Optional[date] —— max(window_end) where status 等于 ok。两者只读、不写库、不加列、不改 DDL。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-05T13:11:20.595Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

仓储加了两个只读聚合方法，让「连续几次没算出东西」可以被读出来

### 完成项

- 新增 list_recent_window_ok_counts：按 window_end 分组统计 ok 条数并倒序
- 新增 get_last_ok_window_end：取最近一次有有效产出的 window_end，从未有过返回 None
- 两个方法均为只读，不加列、不改表结构、不写库
- 既有仓储用例 3 条全部通过

### 改动文件

- `adapters/outbound/repositories/evolution_fitness_repository.py`

### 下一步

t4 消费这两个读数组装空转短语；t7 补两条只读口径用例

---
## 汇报 2（2026-10-05T13:16:09.962Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

收尾汇总：空转读数口落地完成，四段证据齐备

### 完成项

- 四段链全部走完：研发 t-228f42、联调 t-735131、复核 t-1dada1、测试 t-a00ef1
- 研发：两个只读聚合方法落地，不加列、不改 DDL
- 联调：对生产库实跑，读数 10-05=0、10-02=0、09-12=3、09-09=4、09-06=2
- 复核：只读性、索引与口径边界均无偏离
- 测试：仓储用例 3 passed，最近有效产出日读出 2026-09-12

### 下一步

t4 用本卡读数组装空转短语；t7 固化正式口径用例

---
