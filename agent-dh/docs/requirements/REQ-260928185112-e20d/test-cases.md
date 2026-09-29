# 测试用例 · REQ-260928185112-e20d（RTM accepting 覆盖声明的权威来源）

> 口径：每条用例标 `covers:`（覆盖哪些任务卡）与 `validates:`（验证哪些 FR）。
> 归属 = 「该父卡链的测试证据」（父卡 + 其研发/联调/复核/测试四张子卡）。
> 命令与原始输出见 `design/test-cases.md` 与 `verification.md`。

## TC-01: 页面注册 helper 两端同源（看板样板 FR-1）
covers: t-5dc812, t-834096, t-b18667, t-98ea58, t-972c31
validates: FR-1
- 怎么验：`npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts`
- 预期：6 passed；`main.key === sidebar.panellist.id === spec.id`；`grep -c "page-kit" src/client/page/page-panel.ts` = 0

## TC-02: 命令式看板改由宿主挂载（attachBoard，FR-2）
covers: t-48d9a4, t-1c086a, t-711a75, t-32c30f, t-f6b936
validates: FR-2
- 怎么验：`npx vitest run packages/web/dsh-pmboard/tests`（含 attachBoard disposer / 定时器清理断言）
- 预期：相关测试通过；dispose 后 clearInterval 已清、容器监听已移除

## TC-03: 两端注册并接线（index.ts，FR-1/FR-2）
covers: t-75e700, t-2d6d12, t-3d964e, t-5d4b47, t-59970b
validates: FR-1, FR-2
- 怎么验：`pnpm --filter dsh-pmboard build:client`（exit 0 且 [verify-client] OK）；`grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts` 零命中
- 预期：构建三闸通过；旧侧栏底部入口零命中

## TC-04: 跳转语义归位（selectPanel(null)，FR-3）
covers: t-bb1e62, t-88c4f7, t-285f4c, t-b9c1a6, t-f03949
validates: FR-3
- 怎么验：`npx vitest run packages/web/dsh-pmboard/tests`（含 jumpResultMessage 断言）；`grep -rn "closeHostPanel" packages/web/dsh-pmboard/src` 零命中
- 预期：测试通过；补丁符号零命中；E2E 点窗口 chip → activePanelId=null 且会话切换

## TC-05: 拆除旧机制（属性显隐/互斥/壳，FR-4）
covers: t-d52858, t-eed664, t-2ae345, t-bbf54d, t-dcade9
validates: FR-4
- 怎么验：`grep -rnE "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src`（退出码 1）；`pnpm --filter dsh-pmboard build:client`（exit 0）
- 预期：零命中；构建三闸仍过（styles.ts 以 } 收尾、wrap 哨兵未被污染）

## TC-06: 行为等价验证（含 E2E，FR-2/FR-3/FR-4）
covers: t-351435, t-847c36, t-52180d, t-2d637e, t-33a049
validates: FR-2, FR-3, FR-4
- 怎么验：`npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts`；`pnpm --filter dsh-pmboard test` 与开工基线对比；Playwright E2E（:13080）
- 预期：目标测试全绿；全量失败数与基线一致（83，无新增）；E2E 断言 aria-current / 主列渲染 / 跳会话
- 报告：`docs/requirements/REQ-260928185112-e20d/verification.md`

## TC-07: 迁移清单收口（其余 4 页，FR-5）
covers: t-c7f36f, t-10e948, t-c85ab0, t-9a5847, t-26307a
validates: FR-5
- 怎么验：`grep -c "^| " docs/requirements/REQ-260928185112-e20d/migration-checklist.md`（≥6，实测 10）；`grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l`
- 预期：清单存在且四页每行五列齐；同款面板计数实测 4（dsh-pmboard 已迁，见清单 §0 口径）
