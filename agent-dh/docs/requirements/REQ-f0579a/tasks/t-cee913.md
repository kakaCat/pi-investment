# t-cee913 尺寸拆分、杂项清理与全量终验

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
尺寸拆分、杂项清理与全量终验

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
size-budget 转绿（index.ts、styles/base.ts ≤400 行）；npx vitest run 全量 0 失败；tsc --noEmit 绿；pnpm build 成功且 verify-client-build 通过

## 实施方案（implementation）
①index.ts 抽 gate 装配块到新文件（≤400 行）；②styles/base.ts 移一段 CSS 到合适 styles 子文件；③删 src/adapters/CaptureHook.ts.backup；④render/dom-utils.ts renderMarkdown 链接加协议白名单（http/https/mailto/相对路径）；⑤全量终验+git 提交

## 上游产出摘要（dependsSummary）
- 修 verdicts.ts 覆盖通过丢留痕
- 恢复看板视图三处回归
- 精确化操作条 move-req 断言
- 清偿架构门禁债

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
