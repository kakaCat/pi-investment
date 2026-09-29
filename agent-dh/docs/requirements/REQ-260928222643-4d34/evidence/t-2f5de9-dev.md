# t-2f5de9 · 研发段记录（重建客户端产物并发版，完成 TC-15 端到端人工验收）

- 子卡：t-2f5de9（parentId=t-29b629，stageKind=dev，acceptance="改动已落盘，相关测试或命令跑通并附输出摘要"）
- 记录时点：2026-09-29 00:07 CST（= 2026-09-28 16:07 UTC）
- 执行窗口：subagent（t-2f5de9 研发段）
- 本阶段边界：只做本卡范围改动 + 本地验证；**未**执行父卡终态验收命令（全量 vitest / pnpm build:client / pnpm typecheck / restart-with-build.sh 发版 / :13080 人工点击），那些归测试段。

## 1. 本阶段改动（落盘）

| 文件 | 改动 | 理由 |
|---|---|---|
| `packages/web/dsh-pmboard/scripts/verify-client-build.mjs` | `must` 锚点表新增 `dsh-pm-np-board-entry`（FR-1 入口）与 `dsh-pm-np-entry-err`（FR-3 失败提示） | 本卡实施方案含「pnpm build:client 过 WRAP_SENTINEL 哨兵与**产物校验**」。产物校验此前未覆盖本需求的核心 UI 产物（入口按钮 / 失败提示），构建若把它们丢掉门禁不会响——正是 2026-09-15「构建失败不停发版」事故的形状。两个锚点均已确认存在于当前产物（3/2 次命中），门禁由「不覆盖」变为「硬阻断」。 |
| `docs/requirements/REQ-260928222643-4d34/evidence/t-2f5de9-dev.md` | 本记录 | 研发段可复核凭证 |

> 补充说明：`verify-client-build.mjs` 不是打包输入（`build:client` = tsdown(src→lib/client.cjs) → wrap-client → node verify），改它不需要重建产物，已构建的 `lib/client.js` 仍然有效。

## 2. 本卡实现面已落盘（上游卡产出，本卡核验）

| 改动点（父卡 dependsSummary） | 落盘证据 |
|---|---|
| node-panel.ts 加入口按钮、删除「🔄 执行流程」块调用与入参 | `src/client/node-panel.ts:307` 入口按钮（class=dsh-pm-np-board-entry / data-action=np-board-entry）；同文件 `renderProcessFold` 命中 **0**、`执行流程` 命中 **0**；`src/client/node-panel-process.ts` 仍导出该函数（只断调用不删函数） |
| conversation-progress.ts 接线点击→校验→关面板→切看板，删两条留痕拉取 | `src/client/conversation-progress.ts:249`（closest('[data-action="np-board-entry"]')）→ `activateBoardEntry(reqId,{isKnown,requestFocus,layout})` → 失败 `setEntryError` 就地提示不切页（L263）、成功 `closePanel()` + `selectPanel(PANEL_ID)`（L264-265）；失败提示节点 L357（role=alert, class=dsh-pm-np-entry-err）；同文件 `fetchInjectionInfo|fetchIsolationLog` 命中 **0** |
| board-mount.ts 挂载时 takeBoardFocus 初始化 mode | `src/client/board-mount.ts:184` `const focusReqId = boardFocus.takeBoardFocus()` |
| styles/node-panel.ts 新增入口与失败提示两条规则 | L68 `.dsh-pm-np-board-entry`、L73 hover、L76 `.dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err` |

产物面（唯一事实源 = 已构建的 `lib/client.js`，非源码）：`dsh-pm-np-board-entry` 命中 3、`dsh-pm-np-entry-err` 命中 2；`/*WRAP_SENTINEL_MARKER*/` 顶格存在（未被行首注入）。
产物新鲜度：`lib/client.js` 2026-09-29 00:05、`dist/index.mjs` 2026-09-29 00:04，`find src -newer lib/client.js` 为空（无源码晚于产物）。

## 3. 命令与输出摘要

### 3.1 本卡相关测试（5 文件 60 条）
```
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run \
  packages/web/dsh-pmboard/tests/board-focus.test.ts \
  packages/web/dsh-pmboard/tests/board-entry.test.ts \
  packages/web/dsh-pmboard/tests/node-panel.test.ts \
  packages/web/dsh-pmboard/tests/node-panel-styles.test.ts \
  packages/web/dsh-pmboard/tests/board-attach.test.ts
→ Test Files 5 passed (5) / Tests 60 passed (60) / Duration 511ms / exit 0
   （board-focus 5、board-entry 7、node-panel-styles 15、node-panel 27、board-attach 6）
```

### 3.2 产物门禁（standalone 校验，未触发重建）
```
cd packages/web/dsh-pmboard && node scripts/verify-client-build.mjs
→ [verify-client] OK  bundle=307625 bytes, 关键符号齐全, styles.ts 括号配对   exit 0
```

### 3.3 门禁故障注入实测（本次新增锚点是否真的会拦）
```
抹掉产物内 'dsh-pm-np-board-entry'（3 处）→
→ [verify-client] 产物缺少关键符号：dsh-pm-np-board-entry   exit 1   ← 门禁确实拦下
还原后 sha256 与注入前逐字节一致（a6aeefa63fa07be67a8ab53df482c1b8ee50c0fa619b1cebf3202f2020753d79）→
→ [verify-client] OK  bundle=307625 bytes, ...   exit 0
```
（只测成功路径等于没测——故补故障注入，确认新锚点不是装饰。）

## 4. 交接给测试段 / 人工验收

1. 测试段按父卡终态口径执行：`npx vitest run`（全量）+ `pnpm run typecheck` + `pnpm build:client`（含 WRAP_SENTINEL 与本次扩展后的产物校验）+ `node scripts/verify-client-build.mjs`。
2. 发版：`agent-dh/scripts/restart-with-build.sh`（本段未执行）。
3. **TC-15 四步需人工在 :13080 点击**（agent 无浏览器，无法代执行、不得伪造截图）：
   ① 会话里点开流程条任一节点（含分类跳过节点）→ 状态行出现「项目看板 ↗」、面板内**无**「🔄 执行流程」行；
   ② 点入口 → 切到项目看板并显示**该需求详情**，节点面板关闭、会话未被切走；
   ③ 刷新页面 → 看板回默认视图（非粘滞）；
   ④ 用不存在/错误 REQ 触发 → 仍停在会话页 + 可见失败提示（不静默、不白屏、不是列表）。

## 5. 未做的事（显式声明）
- 未跑全量 `npx vitest run`、未跑 `pnpm run typecheck`、未跑 `pnpm build:client`、未执行发版与重启、未在 :13080 做任何点击——均属测试段/人工验收范围（本段边界）。
- 未改动任何本需求源码；本段唯一生产改动为产物校验锚点扩展（见 §1）。
