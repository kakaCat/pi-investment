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
