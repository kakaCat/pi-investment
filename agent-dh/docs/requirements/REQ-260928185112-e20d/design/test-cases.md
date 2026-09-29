# 测试用例 · 页面插槽化迁移 «serves: FR-1, FR-2, FR-3, FR-4, FR-5»

> 上游 `design/migration.md` §行为等价验证设计；结果与原始输出见 `verification.md`。
> 口径：**可证伪**——每条给「怎么验（可复制命令）」与「预期」。

## 1. 用例表

| 编号 | 验什么 | 对应编号 | 怎么验 | 预期 | 实际文件 |
|---|---|---|---|---|---|
| TC-01 | helper 一次注册两端、id 同源、幂等、缺 slots 抛错 | FR-1 | `npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts` | 6 passed | packages/web/dsh-pmboard/tests/client-page-panel.test.ts |
| TC-02 | 两端接线（id/label/order） | FR-1, FR-2 | `npx vitest run packages/web/dsh-pmboard/tests/client-page-register.test.ts` | passed | packages/web/dsh-pmboard/tests/client-page-register.test.ts |
| TC-03 | 薄宿主按 activePanelId 挂载/卸载 | FR-2 | `npx vitest run packages/web/dsh-pmboard/tests/host-panel.test.ts` | passed | packages/web/dsh-pmboard/tests/host-panel.test.ts |
| TC-04 | attachBoard 挂载命令式看板（行为等价） | FR-2 | `npx vitest run packages/web/dsh-pmboard/tests/board-attach.test.ts` | passed | packages/web/dsh-pmboard/tests/board-attach.test.ts |
| TC-05 | 跳会话 = selectPanel(null)+openSession；归档给原因 | FR-3 | `npx vitest run packages/web/dsh-pmboard/tests/session-jump.test.ts` | passed | packages/web/dsh-pmboard/tests/session-jump.test.ts |
| TC-06 | 旧机制符号零命中 | FR-4 | `grep -rE "data-dsh-pm-active\|board-shell\|createBoardShell\|ACTIVE_ATTR\|OTHER_ACTIVE_ATTRS\|closeHostPanel\|ACTIVATE_EVENT" packages/web/dsh-pmboard/src` | 零命中（exit 1） | packages/web/dsh-pmboard/src |
| TC-07 | 旧文件已删 | FR-4 | `ls packages/web/dsh-pmboard/src/client/board-shell.ts packages/web/dsh-pmboard/src/client/footer-action.ts` | No such file | packages/web/dsh-pmboard/src/client |
| TC-08 | 客户端构建过三道门（体积/关键符号/wrap 哨兵） | FR-2, FR-4 | `pnpm --filter dsh-pmboard build:client` | exit 0；`[verify-client] OK …` | packages/web/dsh-pmboard/scripts/verify-client-build.mjs |
| TC-09 | 插件 schema 冒烟不退化 | NFR | `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` | 21 passed | apps/web/tests/plugin-schema.smoke.test.ts |
| TC-10 | 侧栏点击 → 主列渲染 + 选中态 | FR-2 | E2E（Playwright，:13080）：点「项目看板」条目 | 主列渲染看板；按钮 `aria-current="page"` | docs/requirements/REQ-260928185112-e20d/verification.md |
| TC-11 | 点窗口 chip → 面板退出 + 会话切换 | FR-3 | E2E：点卡片窗口 chip | `activePanelId===null` 且 `mainReference.sessionId===目标`；归档会话给明确原因 | docs/requirements/REQ-260928185112-e20d/verification.md |
| TC-12 | 迁移清单存在且五列齐 | FR-5 | `grep -c "^| " docs/requirements/REQ-260928185112-e20d/migration-checklist.md` | ≥6（实测 10） | docs/requirements/REQ-260928185112-e20d/migration-checklist.md |

## 2. 回归基线

- `dsh-pmboard` 全量 `npx vitest run`：**83 failed / 2510 passed / 20 skipped**；failed 数与本次改动前基线一致（无新增红，见 verification.md §2）。
- 未覆盖边界（显式登记，不静默）：见 `verification.md` §6.2（未做项）与 §7.7（观察与边界）。
