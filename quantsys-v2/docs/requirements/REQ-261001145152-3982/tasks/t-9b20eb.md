# t-9b20eb scripts/tools 归位

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
scripts/tools 归位

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 `ls scripts/test_*.py | wc -l` 为 0；5 个一次性脚本已删；`grep -rn "scripts/test_orm" --include='*.md' .` 为 0 或指向新路径；`pytest --collect-only -q` 收集数比迁移前增加。

## 实施方案（implementation）
① 删 5 个已确认 0 引用的日期戳脚本（calibrate_20260723_{v13,v14}_return.py、migrate_20260720_multi_account.py、migrate_20260813_{action_case_unify,scheduler_tasks}.py）；② 14 个误置 test_*.py 从 scripts/ git mv 到 tests/ 并更新文档引用（test_orm*.py 被文档引用 10~11 次，不可盲删）；③ 7 个 _v2/_fixed 补丁产物逐个反查调用方后处理；④ 新脚本一律进已有分类子目录（94 个仍平铺在 scripts/ 根）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
