# t-9ccd5e 删重复实现（零引用项）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
删重复实现（零引用项）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
删除前后 `python -m pytest tests/test_pipeline.py tests/test_integration.py -q` 结果一致；`grep -rn "infrastructure\.quantlib\.adapters\." --include='*.py' .` 只命中该目录内部或为 0；`find . -name "*.bak" -not -path "./venv/*" -not -path "./.venv/*" | wc -l` 为 0。

## 实施方案（implementation）
删除：① infrastructure/quantlib/adapters/ 6 个克隆模块（2068 行，已确认零外部引用）；② infrastructure/quantlib/core/{base_calculator,exceptions}.py（516 行；core/pipeline.py 不可删，tests/test_pipeline.py 与 tests/test_integration.py 直接 import）；③ 13 个 .bak（8097 行，未被 git 跟踪）+ 18 个孤儿 __pycache__ + 9 个空壳包。

## 上游产出摘要（dependsSummary）
- 依赖声明收口（pyproject 为唯一权威）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-01T10:18:52.212Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

这一步做完，变化是：**"同一份东西存在两处、改一处忘一处"的隐患被清掉一万多行**——陈旧的那套适配器实现与两个逐字重复的核心文件删除，只保留一份正本与一个对外转发壳（用它的 8 处代码完全无感），另清掉 13 个备份副本与 27 个空壳目录；测试结果与删除前逐字一致，删除过程中漏掉的一处包内相对导入被测试当场抓到并修好。

### 完成项

- 删除 6 个克隆适配器模块（2,068 行）——保留 `adapters/__init__.py` 转发壳（8 处消费者依赖，实测公共 API 不变）
- 删除 core/base_calculator.py + core/exceptions.py（516 行，与 domain.quantlib.core 下同名文件 md5 逐字相同）；core/__init__.py 与 data_validator.py 改指 domain 正本，对外 API 与 __all__ 不变
- 删除 13 个 .bak（8,097 行，全部未被 git 跟踪）+ 18 个孤儿 __pycache__ + 9 个空壳包 → 合计约 **10,684 行 + 27 个目录**
- 三项验收：pytest 6 failed/11 passed 与删除前逐字一致；外部引用 0；.bak 0
- 回归：新进程端到端可用（/docs、health、K 线读接口）；5 条关键导入全通；业务消费方（factor_layering_service / opportunity_scoring_service / di container）可导入
- **自我纠错并留痕**：首轮删除漏掉包内相对导入（`from .exceptions import`，绝对路径 grep 查不到），被 test_integration 收集失败当场抓到，已改为指向 domain 正本并在代码内注释说明
- 四张子卡（研发/联调/复核/测试）全部完成；复核结论"无偏离"，删除量与审计承诺对齐

### 改动文件

- `infrastructure/quantlib/core/__init__.py`
- `infrastructure/quantlib/core/data_validator.py`

---
