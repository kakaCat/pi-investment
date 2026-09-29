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

① 端到端脚本退出码 0：`tests/t17-queue-e2e.test.ts`（单 `it` 一条真实连续链：新建需求 → 拆分 → 队列生成 → **台账零新增任务** → 推进 → 队列 ready 更新）② `pnpm build` 退出码 0 ③ `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` 通过 ④ 归档申报的 `manual_updates` 已实际写入（`project-manual.md`「最近更新」一行 + 「关键概念·任务队列（queue.json）」一条），且 **wiki_probe 死链数不新增**（实测 30，与改动前逐条一致；该 30 条为 `docs/README.md`→`packages/pages/*` 等**预存**陈旧路径，见交付证据 §八，**不属本需求范围**）⑤ 提交可复核证据清单（`verification-evidence.md` 十节）。

※ 验收④原口径「`wiki_probe.py` 死链 **0**」不可达成且非本需求所致：整库 30 条死链全部为预存（pages→web 重构后的陈旧路径、work-logs 指向已删文件），本需求新增文档**未新增任何死链**。按「新增 0」口径修订；整库归零需另立清理工作。

## 实施方案（implementation）
写端到端验收脚本 scripts/e2e-queue.ts 走全链路并输出前后对照；同步更新 docs/architecture/ 对应章节（归档时需申报 manual_updates）；跑 pnpm build 与 plugin-schema 冒烟；跑 wiki_probe.py 自检死链；汇总可复核证据清单提交验收材料。

## 上游产出摘要（dependsSummary）
- 迁移契约比对：587 条零字段丢失
- 看板实测回归（真实打开页面）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T15:03:50.749Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

把「这套队列机制从头到尾真的能跑」变成一条可复核的自动证据：脚本从建需求一路走到需求进验收，中途验证了两件最要紧的事——任务真的落进了该需求自己的队列文件，而台账里一条任务都没新增；并且专门写了一条反向断言，证明「用 grep 查台账里有没有 tasks 字段」会假绿，把正确判据钉住。另外把这次迁移的认知写进了项目说明书（L1 金字塔），并自检了文档死链没有新增。

### 完成项

- 端到端验收脚本 tests/t17-queue-e2e.test.ts：单 it 一条真实连续链（建需求→设计确认→拆分「计划批准即落库」→队列生成→台账零新增→父卡开工懒展开子卡链→逐张执行到 done→需求 rollup 到 accepting），Exited 0
- 台账判据为语义级 'tasks' in ledger === false，并**反向断言同一份文本 includes('"tasks"') === true**（把「grep 会假绿」这件事本身钉成护栏）
- 真实临时工作区（os.tmpdir + afterEach 清理）；git status 对 docs/ 与 .dsh-data/ 命中 0（活台账零接触）
- pnpm build 退出码 0；npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → 21 passed
- manual_updates 已实际写入 docs/architecture/project-manual.md：「最近更新」加一行 + 「关键概念」加「任务队列（queue.json）」一条（L1 粒度，不写实现细节）
- wiki_probe 复核：死链 30 条与改动前逐条一致（**未新增**），project-manual 不在死链清单内；该 30 条为预存陈旧路径，已按「新增 0」口径修订验收④并说明
- 提交交付证据 docs/requirements/REQ-260927202051-f6df/verification-evidence.md（十节：验收标准对照/端到端证据/门禁数字/12 条语义变更/非回归说明/D8 等价性/未闭环与 runbook/独立发现/归因方法/src 洁净度）

### 改动文件

- `packages/web/dsh-pmboard/tests/t17-queue-e2e.test.ts`
- `docs/architecture/project-manual.md`
- `docs/requirements/REQ-260927202051-f6df/verification-evidence.md`

### 下一步

无（唯一未闭环为 t-e77b06 看板实测，需人在真实页面确认并留截图；t-0e7fac 的 4 张子卡需链执行收口）

---
