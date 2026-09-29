# 测试证据 · REQ-260928222643-4d34

> 执行人：窗口 `session-f17b3bd0` · 时点 2026-09-28 · 工作目录 `packages/web/dsh-pmboard`

## 命令与结果

| # | 命令 | 结果 |
|---|---|---|
| 1 | `npx vitest run tests/board-focus.test.ts tests/board-entry.test.ts tests/node-panel.test.ts tests/node-panel-styles.test.ts tests/board-attach.test.ts` | **5 files / 60 tests passed，0 failed** |
| 2 | `pnpm build:client` | BUILD_EXIT=0；`[verify-client] OK bundle=294486 bytes, 关键符号齐全, styles.ts 括号配对`（WRAP_SENTINEL 无污染） |
| 3 | `grep -n "renderProcessFold" src/client/node-panel.ts` | 无匹配（exit 1）——调用已断；函数本体保留在 src/client/node-panel-process.ts |
| 4 | `grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts` | 无匹配（exit 1） |
| 5 | `grep -c "fetchInjectionInfo" src/client/board-mount.ts` | `1`——看板自己的消费方未被误删 |
| 6 | `grep -n "localStorage\|sessionStorage\|URLSearchParams\|location.hash" src/client/board-focus.ts src/client/board-entry.ts` | 无匹配（exit 1）——一次性、非粘滞 |
| 7 | `npx tsc --noEmit`（过滤到改动文件） | 0 error（仓库其余报错来自其它会话未提交改动） |

## 用例 ↔ 需求映射（源自 design/test-cases.md）

| 需求条款 | 用例 | 实际文件 | 状态 |
|---|---|---|---|
| FR-1 | TC-1 / TC-2 / TC-14 | tests/node-panel.test.ts、tests/node-panel-styles.test.ts | 通过 |
| FR-2 | TC-6 / TC-7 / TC-8 / TC-12 | tests/board-focus.test.ts、tests/board-attach.test.ts、tests/board-entry.test.ts | 通过 |
| FR-3 | TC-9 / TC-10 / TC-11 / TC-13 | tests/board-entry.test.ts | 通过 |
| FR-4 | TC-3 / TC-4 | tests/node-panel.test.ts | 通过 |
| FR-5 | TC-5 | tests/node-panel.test.ts（静态断言 + 反面断言） | 通过 |

任务 ↔ 证据对照（批准计划的 8 张父卡）：

| 任务 | 证据 |
|---|---|
| t-3e952f（board-focus 数据契约） | tests/board-focus.test.ts（5 条） |
| t-dd5ba9（board-entry 接口契约） | tests/board-entry.test.ts（7 条） |
| t-2eb71d（node-panel 入口+下掉） | tests/node-panel.test.ts（26 条）+ grep #3/#4 |
| t-e481a4（conversation-progress 接线） | grep #4/#6 + typecheck #7 + TC-15 人工 |
| t-9b365a（board-mount 消费） | tests/board-attach.test.ts（6 条，含 TC-7/TC-8） |
| t-71aeb3（样式） | tests/node-panel-styles.test.ts（15 条，含 TC-14） |
| t-316227（迁移与兼容） | grep #5 + node-panel-process-map.test.ts 保留 |
| t-29b629（构建发版） | 命令 #2（build:client 过哨兵） |

## 未自动化项（人工验收，:13080）

TC-15 端到端四步：
1. 会话里点开流程条任一节点（含分类跳过节点）→ 状态行出现「项目看板 ↗」，面板里**没有**「🔄 执行流程」那一行；
2. 点入口 → 切到项目看板并显示**这条需求的详情**，节点面板关闭、会话未被切走；
3. 刷新页面 → 看板回默认视图（非粘滞）；
4. 用不存在/错误的 REQ 触发 → 仍停在会话页并有可见失败提示。

## 备注

- 上述命令 #1 之外的全量 `npx vitest run` 在本工作树为红：33 个用例文件失败，均来自**其它会话未提交改动**（改动文件不在失败清单内）。已在 reviews/review-report.md「已知边界」记录。
- 自动实施链执行器在本环境为 no-op（job `reqboard-1` 118ms 空输出），未产出子卡 workflow run 证据；本目录不据此伪造通过结论。

## 覆盖标注（covers ↔ 任务）

> 逐任务标注其测试证据（命令与结果见本文件上方表格）。

### 数据契约 · 一次性交接持有器
covers: t-3e952f, t-1f9da5, t-58ef99, t-017d4e, t-b22075

### 接口契约 · 入口校验与失败提示
covers: t-dd5ba9, t-cb9237, t-bfdf5c, t-687740, t-9aa159

### 面板改造 · 入口按钮与下掉执行流程块
covers: t-2eb71d, t-23961d, t-1d3596, t-bcca7b, t-33f31b

### 接线 · 会话头点击委派与失败提示
covers: t-e481a4

### 消费 · 看板挂载时读取定位意图
covers: t-9b365a

### 样式 · 入口按钮与失败提示
covers: t-71aeb3

### 迁移与兼容核验
covers: t-316227

### 构建发版与端到端验收
covers: t-29b629

## 子卡终态验收 · 一次性交接持有器测试（t-b22075）

> 执行人：实施子代理 · 时点 2026-09-28 23:08 · 工作目录 `packages/web/dsh-pmboard`

- **命令**：`npx vitest run tests/board-focus.test.ts`
- **退出码**：0
- **输出摘要**：`✓ tests/board-focus.test.ts (5 tests) 1ms`｜`Test Files 1 passed (1)`｜`Tests 5 passed (5)`｜`Duration 217ms`｜failed 0 / skipped 0
- **结论**：TC-6 五条用例全绿（requestBoardFocus/takeBoardFocus 取走即清/clearBoardFocus/peekBoardFocus、空串不登记、无 storage/URL 写入），父卡 t-3e952f 的 board-focus 测试阶段验收达成。本阶段为判断/输出型产出，未改动任何代码文件。

## 子卡终态验收 · 入口校验纯函数测试（t-9aa159）

> 执行人：实施子代理 · 时点 2026-09-28 23:12 · 工作目录 `packages/web/dsh-pmboard`

- **命令**：`npx vitest run tests/board-entry.test.ts`
- **退出码**：0
- **输出摘要**：`✓ tests/board-entry.test.ts (7 tests) 3ms`｜`Test Files 1 passed (1)`｜`Tests 7 passed (7)`｜`Duration 210ms`｜failed 0 / skipped 0
- **覆盖用例**：TC-9（layout 未注入 → nav-unavailable，零副作用）、TC-10（REQ 不在台账 → req-missing，零副作用）、TC-10′（空 reqId → req-missing 且不打接口）、TC-11（台账接口失败 → ledger-unreachable，带失败详情）、TC-12（成功路径 → requestFocus 恰好 1 次且不切页）、TC-13（三条失败路径 requestFocus/selectPanel 均 0 次）、boardEntryFailureMessage 三种文案齐备。
- **结论**：父卡 t-dd5ba9 终态验收命令全绿，本测试阶段验收达成；本阶段为判断/输出型产出，未改动任何代码文件（唯一写入为本报告）。

## 子卡终态验收 · 面板入口按钮与下掉执行流程块测试（node-panel.ts 父卡）

> 执行人：实施子代理 · 时点 2026-09-28 23:30 · 工作目录 `packages/web/dsh-pmboard`

- **命令**：`npx vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts`
- **退出码**：0
- **输出摘要**：`✓ tests/node-panel-styles.test.ts (15 tests) 6ms`｜`✓ tests/node-panel.test.ts (27 tests) 5ms`｜`Test Files 2 passed (2)`｜`Tests 42 passed (42)`｜failed 0 / skipped 0｜`Duration 310ms`（vitest v2.1.9）
- **覆盖用例**：node-panel.test.ts 的「项目看板入口（REQ-260928222643-4d34 FR-1 / FR-4）」4 条（TC-1 入口存在/文案固定/带 data-action+data-req 且位于同排相对时间之后、TC-1′ 无相对时间仍渲染、TC-2′ 分类跳过分支同样带入口、TC-3 7 个节点输出均不含「🔄 执行流程」）+「面板侧不再拉取注入/隔离留痕（FR-5）」2 条（TC-5 零引用、TC-5′ 反面断言看板消费方恰 1 处）；node-panel-styles.test.ts 的 TC-14 入口按钮与失败提示样式 3 条（含 head 行 flex-wrap 不裁切）+ 既有 TC-11 作用域断言 12 条。
- **实现面佐证（只读 grep，未改代码）**：`grep -n "renderProcessFold\|ProcessFoldContext\|injection\|isolation" src/client/node-panel.ts` 无匹配（exit 1）；`grep -n "np-board-entry|项目看板 ↗" src/client/node-panel.ts` 命中 L292（入口按钮 + data-action=np-board-entry + data-req）。
- **结论**：父卡（node-panel.ts 加入口按钮并删除执行流程块调用与入参）的终态验收命令全绿，2 文件 42 用例 0 失败；本测试阶段为判断/输出型产出，未改动任何代码文件（唯一写入为本报告）。

## 自动链新增子卡的测试覆盖（covers 标注）

> 2026-09-28 自动链推进后新增的 17 张子卡（链懒展开生成）。它们的覆盖由下列父卡验收命令与对应测试文件承担：
> 接线 / 挂载两族走 `tests/board-attach.test.ts`，样式族走 `tests/node-panel-styles.test.ts`，迁移核验与产物重建走 grep 断言 + `pnpm build:client`。

- covers: t-9f7598, t-e3785d, t-43763b, t-86d2f9（parent t-e481a4 · conversation-progress 接线，命令见卡面 acceptance）
- covers: t-1725e5, t-fe79d8, t-95a1f1, t-f8052d（parent t-9b365a · board-mount 挂载消费）
- covers: t-0fc58f, t-c5ae63, t-defa17, t-95e056（parent t-71aeb3 · styles/node-panel 两条规则）
- covers: t-4397da, t-a2ba2f, t-b447b1（parent t-316227 · 无 schema 变更 + 零回归）
- covers: t-2f5de9, t-247597（parent t-29b629 · 重建客户端产物）
