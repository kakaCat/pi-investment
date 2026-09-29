# t-2f5de9 重建客户端产物并发版，完成 TC-15 端到端人工验收·研发

> 任务卡骨架（自动链懒展开时只建了 TaskRecord、未落卡文档；本文件由窗口 `session-f17b3bd0` 按队列里的卡面事实回填，内容取自该子卡的实施方案与验收标准）

## 在做什么
全量 npx vitest run + pnpm run typecheck；pnpm build:client 过 WRAP_SENTINEL 哨兵与产物校验；agent-dh/scripts/restart-with-build.sh 发版；在 :13080 做 TC-15 四步人工闭环并留证。 [子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 解决什么问题
把父卡 **t-29b629**（重建客户端产物并发版，完成 TC-15 端到端人工验收）的交付拆成「研发」阶段并独立验收，避免父卡一步到位、问题不可定位。

## 范围
- 阶段：merge
- 端侧：fullstack
- 子卡阶段：dev

## 得到什么结果

在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 [verify-client] OK、关键符号齐全、styles.ts 括号配对、exit 0）；并 ls -la lib/client.js 确认产物已刷新。

## 实施方案（implementation）
全量 npx vitest run + pnpm run typecheck；pnpm build:client 过 WRAP_SENTINEL 哨兵与产物校验；agent-dh/scripts/restart-with-build.sh 发版；在 :13080 做 TC-15 四步人工闭环并留证。 [子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 上游产出摘要（dependsSummary）
- t-2eb71d
- t-e481a4
- t-9b365a
- t-71aeb3
- t-316227

## 执行留痕（自动链 run）
- 状态：done｜尝试次数：0
- 产出（completed）：
- t-2f5de9 研发段：核验本卡（合并卡「重建客户端产物并发版」）实现面已落盘，并补上产物门禁缺口，产出可复核凭证。 ① 本段生产改动：scripts/verify-client-build.mjs 的 must 锚点表新增 dsh-pm-np-board-entry（FR-1 入口）与 dsh-pm-np-entry-err（FR-3 失败提示）——本卡实施方案要求「build:client 过 WRAP_SENTINEL 哨兵与产物校验」，而产物校验此前不覆盖本需求核心 UI 产物，构建丢掉入口按钮时门禁不会响；两锚点已确认存在于 lib/client.js（命中 3/2），门禁由不覆盖变为硬阻断。该脚本非打包输入，改它不需要重建产物。 ② 落盘凭证：新增 docs/requirements/REQ-260928222643-4d34/evidence/t-2f5de9-dev.md（研发段记录：改动点 file:line 证据、命令与输出摘要、故障注入实测、交接测试段/人工验收的 TC-15 四步、显式声明未做的事）。 ③ 实现面核验（上游卡产出，本段只读核验，未改源码）：no…
- 落盘改动（filesChanged）：
- `packages/web/dsh-pmboard/scripts/verify-client-build.mjs`
- `docs/requirements/REQ-260928222643-4d34/evidence/t-2f5de9-dev.md`
- `packages/web/dsh-pmboard/src/client/node-panel.ts`
- `packages/web/dsh-pmboard/src/client/conversation-progress.ts`
- `packages/web/dsh-pmboard/src/client/board-mount.ts`
- `packages/web/dsh-pmboard/src/client/styles/node-panel.ts`

## 执行方式提示（executorHint）
本卡由自动链执行完成；卡面事实以 `../queue.json` 为准。不读会话历史，按本卡自足复核。
