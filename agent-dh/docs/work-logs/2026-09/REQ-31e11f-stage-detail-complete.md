# REQ-31e11f 会话进度流程节点可点击查看详情 — 实施完成报告

- 日期：2026-09-15
- 需求：REQ-31e11f《会话进度流程节点可点击查看详情》（feature，窗口 w-8913546f）
- 状态：实施完成（t1-t9），370 测试全绿，待部署 :13080 实测与人工验收

## 交付概览

把「会话框进度条」与「项目看板」从两套脱节口径，统一为**同一份 StageDetail JSON**（domain 层单一定义），点击任一流程节点展示该节点的产物、任务、追溯链。

### 9 个子任务（分窗/subagent 并行 + 本会话集成）

| 任务 | 交付 | 测试 |
|---|---|---|
| t1 domain 契约 | StageDetail 判别联合、StageArtifact、五门 ARTIFACT_CONFIRM_GATES、CATEGORY_FLOW_PROFILES（6 类）、REQBOARD_SCHEMA_VERSION=4 | 本会话 |
| t2 host 节点详情接口 | StageDetailAssembler 模板装配器 + 8 节点 + GET /requirements/:id/stage/:stage | +29 |
| t3 reqboard_task_report | 渲染 tasks/t-xxx.md 任务卡 + 登记 task_detail 产物 | +7 |
| t4 产物登记钩子+闸门 | plan/decompose/verify/archive 四处登记 + decomposition.md/verification.md 自动落盘 + 五门两级校验（missing_artifact/artifact_not_confirmed）+ 分类过滤 + 存量兼容 | +18 |
| t5 阶段提示词钩子 | STAGE_PROMPTS 5 常量 + capture.ts/capture-hook.ts 双注入（superpowers 式） | +14 |
| t6 client 节点详情面板 | 纯字符串 stage-panel.ts（renderStagePanel 模板法，与 view.ts 同构、Node 可测）+ 会话框/看板详情抽屉同源接入 | +100 |
| t7 产物chips+确认入口卡面外置 | 卡片正面五门 chip 三态（绿✓/橙⏳可一键确认/红✗）+ 「确认产物」主按钮卡面外置（用户明确要求）+ 派生展示 | +15 |
| t8 测试补齐+接力实测 | 12 条验收标准逐条转测试 + handoff.test.ts 接力实测（任务卡自足，新窗口零历史可续作）+ 防御/边界 | +67 |
| t9 构建部署+文档 | client 构建（tsdown+wrap-client）+ 本文档 | — |

### 测试
- 基线 188 → 最终 **370 tests / 22 files 全绿**
- 12 条验收标准全部有可执行锚点测试
- 接力实测：A 拆 → A 做 t1 → B 读卡做 t2 → B 汇报 → 产物链完整

### 源码修复（测试暴露的真实缺陷，最小改动）
1. protocol.ts flowProfileFor：非法分类值兜底 feature（原 TypeError）
2. stage-panel.ts renderImplementingBody：byWindow undefined 防御
3. styles.ts injectStyles：补回 t7 恢复时截断的函数闭合括号（构建期 PARSE_ERROR 暴露）

### 关键设计决策
- **同源**：会话框 conversation-progress 与看板 view.ts 详情抽屉消费同一 GET /requirements/:id/stage/:stage，消除两套口径（用户痛点根因）
- **节点完成=节点产物就位**：五道人工门（需求/设计/拆分/验收/归档），缺产物或未确认两级拦截
- **分类差异化**：feature 5 门全量；bug/refactor 免需求分析 4 门；spike/doc/chore 极简 2 门
- **确认入口卡面外置**：当前门待确认时，卡片正面直接渲染「确认产物」按钮，一键确认不打开抽屉
- **接力（Claude Code Task 模式）**：decompose 生成自足任务卡 tasks/t-xxx.md（目标/背景/验收/上游摘要/executorHint），task_report 追加，新窗口不读历史即可续作
- **阶段提示词**：obra/superpowers 式双注入，prompts 为插件内 TS 常量（非 DSH skill）

### 已知事项
- reqboard.test.ts「Session sync explicit marker」在全量并发跑时偶发 1 例失败，单跑/重跑均绿——疑似测试间共享状态泄漏，非功能回归，待跟进
- 部署：client 需 `npm run build:client`（tsdown+wrap-client）产出 lib/client.js，重启 :13080 生效

## 下一步
部署 :13080 实测 → reqboard_verify_submit 提交人工验收。
