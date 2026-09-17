# REQ-422af1 验收（verification）

> 自动生成于 reqboard_verify_submit

## 验收结论
REQ-422af1 交付完成：节点提示词从「单份常量」改为「节点×难度×立项类型」路由解析（126 条分片记录；heavy = vendor superpowers v6.3.0 原文逐字节不改，light 自写精简），并落地同窗口 surface 整段替换的节点隔离（默认关）。12 张任务卡全部完成，每张经父窗口独立复核。最终门禁：tsc 0 错误、包内全量 940 passed（唯一失败为改动前既有基线）、四条机械门禁 21/21、客户端哨兵 OK。已重启部署并线上核验：注入留痕只读接口返回真实记录（routeKey=implementing/light/feature、hitLevel=exact、4 个片段、charCount=1084），流程节点接口 200 无 500 回归。另修复本需求引入的回归（提示词分片曾进浏览器包，bundle 293,225→209,934 字节）。三个已知缺口已在证据中显式列出。

## 证据清单
- 线上证据① 注入留痕只读接口 200：curl "http://127.0.0.1:13080/dashboard/api/reqboard/injection-log?window=session-41e7e4cd-...&k=5" → {"success":true,"data":{"entries":[{"stage":"implementing","difficulty":"light","category":"feature","routeKey":"implementing/light/feature","hitLevel":"exact","fragmentIds":["implementing/light/feature","implementing/light","implementing/feature","common/iron-rules"],"charCount":1084}],"total":1,"available":true}} —— 精确命中①且合成「节点档 + 类型档 + 铁律」，设计语义在线上成立；留痕文件 .dsh-data/state/prompt-injection-log.json
- 线上证据② 流程节点接口无回归：GET /dashboard/api/reqboard/session/<window>/progress → http=200，返回 REQ-422af1 进度与 closed=false（重启前曾有 500 事故，本次未复现）
- 线上证据③ 客户端产物：lib/client.js = 209,934 字节（修复前 293,225），grep "Three Paths" = 0，提示词分片已不进浏览器包
- 门禁① 类型检查：npx tsc --noEmit -p tsconfig.json（workdir=packages/pages/dsh-pmboard）→ exit 0，0 错误
- 门禁② 包内全量套件：npx vitest run（workdir=packages/pages/dsh-pmboard）→ Test Files 1 failed | 61 passed；Tests 1 failed | 940 passed；唯一失败为 packages/pages/dsh-pmboard/tests/board-info-fixes.test.ts（改动前既有基线，改动前实测 1 failed | 628 passed）
- 门禁③ 四条机械门禁：npx vitest run packages/pages/dsh-pmboard/tests/layer-boundary.test.ts packages/pages/dsh-pmboard/tests/size-budget.test.ts packages/pages/dsh-pmboard/tests/typecheck.test.ts packages/pages/dsh-pmboard/tests/message-hygiene.test.ts → 21/21 passed
- 门禁④ 客户端构建哨兵：pnpm build:client + node packages/pages/dsh-pmboard/scripts/verify-client-build.mjs → "[verify-client] OK bundle=209934 bytes, 关键符号齐全, styles.ts 括号配对"；对新增符号 dsh-pm-injection-info 做故障注入可使其 exit 1，恢复后复绿
- 门禁⑤ 提示词六条门禁 + 故障注入：packages/pages/dsh-pmboard/tests/prompt-gates.test.ts 正常态 13/13；六条各自故障注入（删兜底分片 / 插 reqboard_legacy_probe / 预算调极小 / 孤岛与重复 id / 删「下一步」行 / 改 md 不重建）全部 exit 1 变红，恢复后复绿
- 门禁⑥ 源产物同步：node packages/pages/dsh-pmboard/scripts/check-prompt-fragments.mjs → OK（fragments/**.md 与 generated/fragments.ts 一致，且 heavy.md ↔ vendor 原文逐字节一致）
- 等价性证据（P0 零行为变更）：基线快照 packages/pages/dsh-pmboard/tests/fixtures/stage-prompts-baseline.json 与改造后解析结果 6 个 stage 逐字一致（771/721/716/796/625/862 字节，diff=equal）；packages/pages/dsh-pmboard/tests/stage-prompts.test.ts 断言未改且 21/21 绿
- vendor 证据：14 份 SKILL.md 与 obra/superpowers origin/main（commit b36e082 / tag v6.3.0 / MIT）逐字节一致（父窗口 cmp 逐份复核：一致 14、不一致 0）；packages/pages/dsh-pmboard/src/domain/prompt/fragments/brainstorming/heavy.md 与 packages/pages/dsh-pmboard/src/domain/prompt/vendor/superpowers/brainstorming/SKILL.md cmp 逐字节一致（15,456 字节 / 250 行）
- 开关安全性证据：NODE_ISOLATION 默认关；packages/pages/dsh-pmboard/tests/isolate-node-context.test.ts 29/29，关态 stats()={scheduled:0,executed:0,replaced:0,failed:0} 且隔离端口一次未建；故障注入（摘掉 if(!deps.enabled) return）恰好让 2 条关态用例变红后已还原并复绿
- 已知缺口①（不掩盖）：开态（NODE_ISOLATION=on）在真实窗口的替换未实测 —— 生产 idle 探针依赖 sessionProjections.turnBoundary，判不出时保守判不空闲，可能落 skipped/agent_busy 留痕；开关默认关，无生产行为变更，开启前需实机观察一次
- 已知缺口②：按需片段（test-driven-development / subagent-driven-development / using-git-worktrees / dispatching-parallel-agents / requesting+receiving-code-review / systematic-debugging / writing-skills / using-superpowers 共 8 份）仅 vendor 落盘、未注册为分片（注册即需被路由或 include 命中，否则违反「无孤岛」门禁 4）→ 留待「节点内子步骤」设计
- 已知缺口③：wiki_probe 基线仍有 2 死链 + 1 孤儿，来自 docs/INDEX.md（该文件未改动，HEAD 既有），与本需求无关；探针改动见 scripts/wiki_probe.py
- 偏离裁决记录（父窗口裁定，非静默）：P0 三处偏离（常量表改派生视图 / 链声明走结构化表 / 铁律 P0 空文件）见 docs/requirements/REQ-422af1/decomposition.md §6；t12 修改 scripts/wiki_probe.py 增加 fragments/vendor 路径排除（vendored 第三方原文自带上游 front-matter 被误判为 wiki 页；逐字节门禁禁止改写 vendor）亦经裁定接受
- 复核纪律证据：12 张卡无一采信自述 —— 父窗口逐张重跑命令、亲手做故障注入、cmp 核对 vendor 字节；并抓出两处自述与实际不符后更正（调用点 3 vs 2 实为兼容壳 StagePromptSpec.ts:25；文档「类型档尚未落地」表述在 t8 已落地后过期，见 docs/architecture/workflow-stages.md）
