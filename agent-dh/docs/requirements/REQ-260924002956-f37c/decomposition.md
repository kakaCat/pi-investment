# 拆分计划 · REQ-260924002956-f37c

目标：把立项拒绝路径做成**终端路径**——拒绝即收框、即返回、不登记闸门、不发"未通过"投递（BUG-1 + BUG-2），并在 H4 堵掉"无 from 的闸门印出现状"这一分支。分四卡：复现（红）→ 修复（绿）→ 回归（含边界与全量）→ 真机验证。

做法：契约已在 `design/design.md`「数据契约与接口」定死（`AskQuestion`/`AskAnswer`/`CaptureMapping`/工具出参/留痕结构全部不变）；改动集中在 `src/application/internal/capture-mapping.ts`（题目拆两段）、`src/application/use-cases/CaptureRequirement.ts`（拒绝短路 + G0 登记挪段）、`src/application/gate/handlers/h4-resume.ts`（无 from 不编现状）。实施卡按契约落地；无迁移、无兼容负担（既有断言口径保持不变）。

## 任务表

| key | title | phase | side | depends_on | requirement_refs |
|-----|-------|-------|------|-----------|------------------|
| t1 | 固化拒绝路径复现：加三条失败用例（红） | test | backend | — | BUG-1,BUG-2 |
| t2 | 修复：题目拆两段 + 拒绝短路 + G0 挪段 + H4 无 from 不编现状 | implement | backend | t1 | BUG-1,BUG-2 |
| t3 | 回归：肯定路径不变 + 无 from 文案边界 + 全量 vitest | test | backend | t2 | BUG-1,BUG-2 |
| t4 | 真机验证：重启加载后实走一次拒绝路径 | test | backend | t3 | BUG-1,BUG-2 |

说明：t1 先跑出红（证明复现成立、且断言真的在测这条路径）；t2 只动上面三个文件，禁止顺手重构其它分支；t3 是"修好了"的独立证据（回归卡不与修复卡合并）；t4 需要重启实例（会话短暂中断），以"弹框立即收 + 无后续追问 + 无投递"为判据。t1 的失败用例即未来的回归防线，长期保留。

## 验收口径（每卡可证伪）

- **t1**：`npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts packages/web/dsh-pmboard/tests/gate-handlers.test.ts` —— 新增断言在**未修复代码**上失败，红项列出（拒绝路径 ask 次数 > 1 / G0 入队 > 0 / 文案含「节点仍在」至少其一）。
- **t2**：同命令转绿；`git diff --stat` 只含上述三个源文件。
- **t3**：`npx vitest run packages/web/dsh-pmboard` 全绿；额外断言：有 `from` 的闸门负分支文案仍含「节点仍在 {from}」（防"修反"）。
- **t4**：重启后走一次拒绝路径——弹框选「✖️ 不需要立项」后立即关闭、无类型/难度/文档位置追问、回合结束无「闸门待改进」投递；证据：`state/capture-rejections.json` 新增记录 + 会话内无该投递。
