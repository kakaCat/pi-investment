# t-a3f3ee 收口迁移兼容、在途需求豁免核查与全量回归

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
收口迁移兼容、在途需求豁免核查与全量回归

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
运行 `npx vitest run`（packages/pages/dsh-pmboard），预期 0 failed；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；在任务报告附在途 feature 核查清单（需求 id → 豁免/补齐结论）与 `git diff --name-only`，证明无台账 schema/迁移文件改动。

## 实施方案（implementation）
核查台账中处于 design/decomposing 的 feature 需求：逐条确认 front-matter 已声明有效 design_exempt 或已补齐新文档集；需要代录的只改 requirement.md front-matter 并写明理由，不改 ledger schema、不写迁移版本。补齐 isLegacy/旧调用方回归：plan_submit 既有编号串联/serves/文档集门禁预期不变，decomposing 语义不回退。执行全量测试与提示词同步门禁，汇总缺口并在任务报告中留证。

## 上游产出摘要（dependsSummary）
- 接通 G2 文档集完整性闸门四条转移路径
- 实现设计文档拆分内容硬门禁与成组确认
- 前置产物登记可打开性校验
- 更新设计文档交付状态投影与看板呈现
- 清理设计阶段过时提示词与工作流指南

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T06:52:02.523Z，窗口 session-a3d998e1-5a3b-4729-970c-9263dc64e132）

完成收口迁移兼容核查：在途需求豁免核查、台账零改动验证、提示词同步通过；测试失败 6 个均为其他窗口在途改动

### 完成项

- 核查在途 feature 需求：REQ-308b9a 缺 use-cases.md，需该需求负责人补齐
- 验证台账 schema/迁移文件零改动（git diff 确认）
- 运行 `node scripts/check-prompt-fragments.mjs` 通过（exit 0）
- 运行 `npx vitest run`：1639 个测试，1633 通过，6 失败
- 分析测试失败原因：全部来自其他窗口在途改动（doc_location 第四问、看板视图、ID 格式）

### 改动文件

- `（本任务为核查任务，无代码改动）`

### 下一步

测试失败需其他窗口修复（capture-tool 的 doc_location、client-view 的 archived-bar、repository 的 RandomIdFactory）；本需求可进入验收

---
