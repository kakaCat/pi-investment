# t-6cfab3 打零参绑定 patch

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
打零参绑定 patch

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/zero-arg-binding.test.ts 全绿且断言 patch 后 lib/process.js 绑定工厂为 (args = {})；在本窗口 run_code 内只调 tools.reqboard_status()（零参）→ 正常返回，输出无 binding arguments must be lossless JSON

## 实施方案（implementation）
新增 patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch（lib/process.js 绑定工厂 value: (args = {})，唯一改动）+ 根 package.json pnpm.patchedDependencies；新增 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
