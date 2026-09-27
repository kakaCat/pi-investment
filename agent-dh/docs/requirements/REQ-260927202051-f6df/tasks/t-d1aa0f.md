# t-d1aa0f 端到端验收与文档同步

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端验收与文档同步

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：doc

## 得到什么结果
① 端到端脚本 `node --import tsx/esm scripts/e2e-queue.ts` 退出码 0（新建测试需求 → 拆分 → 队列生成且台账无新任务 → 推进 → ready 更新）；② `pnpm build` 退出码 0；③ `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` 通过；④ `python3 agent-dh/scripts/wiki_probe.py` 死链数 0；⑤ 提交可复核证据清单（命令 + 输出摘要 + 队列文件路径 + 页面截图路径）。

## 实施方案（implementation）
写端到端验收脚本 scripts/e2e-queue.ts 走全链路并输出前后对照；同步更新 docs/architecture/ 对应章节（归档时需申报 manual_updates）；跑 pnpm build 与 plugin-schema 冒烟；跑 wiki_probe.py 自检死链；汇总可复核证据清单提交验收材料。

## 上游产出摘要（dependsSummary）
- 迁移契约比对：587 条零字段丢失
- 看板实测回归（真实打开页面）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
