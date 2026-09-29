# t-3b5f9c 先定契约：挂起确认能标出「被中止」，判定口径只留一处·联调

> 需求：REQ-260927123256-196b pm 确认弹框改为真正阻塞（与原生 ask_user_question 等待语义对齐）
> 父卡：t-f8ed18

## 在做什么
把「中止留痕 + 台账是否已落章」这条链从注册表一路走到回执，确认跨模块接缝读的是同一份事实。

## 解决什么问题
新增的 `markInterrupted` / `interruptedAt` 只有在 adapter → 回执 → 守卫这条链上都认同一份事实时才有意义。
联调就是确认接缝没有「各自判定」——这是「判定口径只留一处」能否成立的关键一步。

## 范围
- 阶段：integrating
- 端侧：backend
- 父卡：t-f8ed18

## 得到什么结果
`node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts` 全绿（7 例）：
注册表 `markInterrupted` 对未知 ticket 不抛；回执在「已中止且未作答」时给出中止文案；
共享谓词与台账落章一致；`PendingConfirmPort` 运行时形状为 5 方法。

## 实施方案（implementation）
跑 t1 的联调用例 `tests/pending-guard-integration.test.ts`，逐条核对 registry → ConfirmReceipt → 守卫的接缝；
对不通过项回到对应实现文件定位（不改口径，只修接缝）。

## 上游产出摘要（dependsSummary）
- 研发 t-a0c273：协议字段 / 端口方法 / 注册表实现 / pending-guard 单点谓词 / 回执改用共享谓词

---
## 汇报 1（2026-09-27，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

这一步做完：注册表、回执、守卫三处对「是否被中止 / 是否已落章」读的是同一份事实——联调用例 7/7 全绿。

### 完成项

- 注册表 `markInterrupted` 对未知 ticket 返回 undefined 且不抛（经真实工具返回码复核）
- 过期基准 `(interruptedAt ?? createdAt) + ttlMs` 在 adapter 侧生效（中止记录不因登记早而提前失效）
- 回执链路改用共享谓词 `targetConfirmedInLedger`；`interruptedAt` 且未作答时给出「等待已被中止」文案
- 端口运行时形状 = `register/get/settle/pendingForWindow/markInterrupted`

### 改动文件

- `packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts`（联调用例，7 例）

### 下一步

复核子卡 t-738238 逐条比对设计与实现；测试子卡 t-db1d48 复跑验收命令。

---
