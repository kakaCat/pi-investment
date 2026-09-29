---
requirement: REQ-260927123256-196b
kind: test-coverage
---

# 测试覆盖标注 · REQ-260927123256-196b

> 供 RTM accepting 覆盖度门禁读取（`covers: t-xxx` = 该用例覆盖的任务卡）。
> 用例明细与命令输出见 `design/test-cases.md` 与 `tests/test-evidence.md`。

## TC-1: 缺省阻塞——ask 永不 resolve 时工具 200ms 仍未返回
covers: t-4d87e5, t-93e425
validates: FR-1
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts

## TC-2: 阻塞中登记未作答记录（守卫拦写），作答返回后守卫释放
covers: t-4d87e5, t-fd257f, t-93e425
validates: FR-1, FR-2
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts

## TC-3: 显式宽限才非阻塞；未装配能力 / 非法值显式拒绝
covers: t-4d87e5, t-93e425
validates: FR-3
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts

## TC-4: 中止留痕——pending+ticket+interrupted，status 可见，写路径仍被拒
covers: t-f8ed18, t-4d87e5, t-93e425
validates: FR-4
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts

## TC-5: 取消——中性返回、无 pending/ticket、守卫放行、台账无落章
covers: t-4d87e5, t-93e425
validates: FR-1, FR-6
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts

## TC-6: 停手守卫拦写与台账落章即解除（不死锁）
covers: t-fd257f, t-93e425, t-a0c273
validates: FR-2, FR-4
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts

## TC-7: reqboard_status.pending_confirms 投影与陈旧记录过滤
covers: t-fd257f, t-93e425
validates: FR-4
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts

## TC-8: 契约形状——端口 5 方法 / PendingConfirmation 增 interruptedAt / 回执 4 键不变
covers: t-f8ed18, t-a0c273, t-3b5f9c, t-738238, t-db1d48, t-93e425, t-2231a8
validates: FR-4, FR-6
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/contract-shapes.test.ts packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts

## TC-9: 文案契约——工具描述/提示词含「缺省阻塞」
covers: t-16cefa, t-93e425
validates: FR-5
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts

## TC-10: 兼容性回归——既有确认链路不退化
covers: t-2231a8, t-93e425
validates: FR-6
命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts packages/web/dsh-pmboard/tests/contract-shapes.test.ts
