# REQ-a8d582 验收（verification）

> 自动生成于 reqboard_verify_submit

## 验收结论
看板验收环节按 REQ-a8d582 交付：FR-1「验收通过」点击先弹确认框（列出不通过/未裁决条数与不合格项摘要，取消则零请求）；FR-2 逐项裁决只记录，不再自动打回实施、不再自动建返工卡，退回由人点「退回返工」触发（看板与 agent 弹框两条通道统一）；FR-3 显示条件只看阶段——进入验收态就展示「验收通过」，旧提示文案移除；FR-4 不合规通过（有不合格项或无验收材料）必须带 confirm_override，缺失返回 400 verify_override_required；带覆盖则写 acceptanceOverride + 需求评论 + 状态事件三处留痕，全过且材料齐全的通过不写覆盖。实现期一处修正并已同步设计文档：覆盖记录落点由 verification.override 改为需求级 acceptanceOverride（无材料通过时没有 verification 对象可挂）。注入文案同步：accepting 轻档与 heavy 覆盖条目已改为新语义，并重跑片段基线与一致性检查。

## 证据清单
- 命令：cd agent-dh/packages/pages/dsh-pmboard && npx vitest run（五个用例文件：board-info-fixes / client-view / verdicts-and-rework / verify-override / e2e-accept-override）—— 结果 Test Files 5 passed / Tests 83 passed
- 命令：cd agent-dh/packages/pages/dsh-pmboard && pnpm build:client —— 退出码 0；[verify-client] OK 关键符号齐全；产物 packages/pages/dsh-pmboard/lib/client.js 231155 bytes，新于源码最新改动，含 confirm_override 与 覆盖通过 字面量
- 命令：cd agent-dh/packages/pages/dsh-pmboard && npx vitest run（prompt-baseline / prompt-router / prompt-gates / stage-prompts / prompt-tiers）—— 122 passed；node packages/pages/dsh-pmboard/scripts/check-prompt-fragments.mjs 报 OK（生成物与片段源一致）
- 覆盖语义用例：packages/pages/dsh-pmboard/tests/verify-override.test.ts —— 缺覆盖→400 verify_override_required 且状态不变；带覆盖→archived 且 acceptanceOverride/评论/状态事件三处留痕；无材料+覆盖→archived 不报 missing_artifact；无材料无覆盖→400；全过不带覆盖→照常 archived 且不写覆盖
- 端到端用例：packages/pages/dsh-pmboard/tests/e2e-accept-override.test.ts —— 跨层：裁决不通过仍在验收态 → 看板文案装配 verifyConfirmCopy → 覆盖通过 → 台账 → 客户端重渲染按钮消失
- 主要改动文件：packages/pages/dsh-pmboard/src/client/views/stage-detail.ts、packages/pages/dsh-pmboard/src/client/board-mount.ts、packages/pages/dsh-pmboard/src/client/api.ts、packages/pages/dsh-pmboard/src/client/types.ts、packages/pages/dsh-pmboard/src/http/routers/verdicts.ts、packages/pages/dsh-pmboard/src/http/routes.ts、packages/pages/dsh-pmboard/src/application/internal/verdicts.ts、packages/pages/dsh-pmboard/src/application/use-cases/AcceptSheet.ts、packages/pages/dsh-pmboard/src/domain/workflow/AcceptanceSheetSpec.ts、packages/pages/dsh-pmboard/src/shared/protocol.ts
- 设计文档（含实现期修正留痕）：docs/requirements/REQ-a8d582/design/data-model.md、docs/requirements/REQ-a8d582/design/interfaces.md、docs/requirements/REQ-a8d582/design/test-cases.md
- 【残差如实列出，非本需求改动】全量 npx vitest run 当前 74 passed / 29 failed（files）：加载失败根因是 packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/generate-workflow-script.ts 第 7 行反引号转义导致的语法错误（同事窗口未提交文件），其余失败亦落在其未提交的 TaskExecuteTool 与 TaskStatusTool 目录；本窗口按仓库纪律未改动这些文件
- 【遗留待办（非本需求范围）】:13080 浏览器侧尚未做人工四条路径实测：页面插件 client 由 Web 产物消费，需重建 Web 产物并刷新（可能需重启 :13080，会中断会话），未在无人点头时执行
