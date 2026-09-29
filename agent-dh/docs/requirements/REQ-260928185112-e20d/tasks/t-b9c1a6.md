# t-b9c1a6 跳转语义归位（selectPanel(null)）·复核

> 需求：REQ-260928185112-e20d · 父卡：t-bb1e62 · 阶段：implement/frontend · 子卡阶段：review · 状态：done

## 在做什么
跳转语义归位（selectPanel(null)）·复核

## 解决什么问题
子卡阶段：复核

## 得到什么结果（验收标准）
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 实施方案
改 packages/web/dsh-pmboard/src/client/session-jump.ts：删除 closeHostPanel() 与其 dsh-pmboard:open-board 派发；jumpToSession 改为先经 page-runtime 调 layout.selectPanel(null) 再 uiWorkspace.openSession(sid)；layout 不可用时返回 unavailable（不静默）；保留 archived/missing 判定与既有提示文案。

[子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 完工记录（物化自实施链 workflow run 的 lastReport）
- {
  "filesChanged": [],
  "completed": [
    "【结论】本卡范围内（packages/web/dsh-pmboard/src/client/session-jump.ts + page/page-runtime.ts + src/client/index.ts inject + package.json）与设计无功能偏离；逐条结论见下 1-8。",
    "1) 设计『删除 closeHostPanel() 与其 dsh-pmboard:open-board 派发』(design/architecture.md:164) → 无偏离。依据：grep -rn closeHostPanel packages/web/dsh-pmboard/src 零命中；session-jump.ts 内 CustomEvent/dispatchEvent 零命中。",
    "2) 设计『先 layout.selectPanel(null) 再 uiWorkspace.openSession(sid)』(architecture.md:165) → 无偏离。依据：session-jump.ts:167-176；tests/session-jump.test.ts:79 断言时间线 ['selectPanel:null','openSession:s-target'] 通过。",
    "3) 设计『目标会话即当前会话时同样先回对话、只省 openSession』(architecture.md:166) → 无偏离。依据：session-jump.ts:167-171（URL 命中路径，测试 8/8 中两条覆盖）。观察（非偏离）：refresh 后命中分支未二次判 current，会多调一次 openSession(当前会话)，语义无害。",
    "4) 设计『layout 来自 apply() 交模块级 page-runtime，session-jump 经它读』(architecture.md:168-169) → 无偏离。依据：index.ts:62 setPageLayout(ctx.layout)、index.ts:83 dispose 时 clearPageLayout；session-jump.ts:25 import getPageLayout；page-runtime.ts 零 import（自包含纪律）。",
    "5) 设计『模块 inject 与 package.json dsh.client.inject 同步加 layout』(architecture.md:170-171) → 无偏离。依据：index.ts:26 含 'layout'；git diff HEAD package.json 仅把 inject 数组扩为 [...,'workspaces','layout']。",
    "6) 父卡/设计『layout 不可用返回 unavailable（不静默）』 → 无偏离。依据：session-jump.ts:121-125 在 archived/missing 判定之前返回 'unavailable'；测试『layout 未注入 → unavailable，且不 openSession』时间线为空。",
    "7) 设计 FR-3『归档会话保持现状（可点 + data-archived + 明确文案），不静默』 → session-jump 侧无偏离（session-jump.ts:229-234 alert 文案保留）。渲染侧 dom-utils.ts:107-109 仍带 data-action=jump-session 且 data-archived=true（board-info-fixes.test.ts:292 通过）。仅 styles/board.ts:127 注释陈旧（称『不可点（不带 data-action）』），但无 pointer-events:none、仅视觉淡化，无行为偏离。",
    "8) 父卡『保留 archived/missing 判定与既有提示文案』 → 判定与 handleSessionJump 三处 alert 保留（session-jump.ts:223/231/249/253）。连带发现（须移交）：board-mount.ts:151-152 的 jumpResultMessage('unavailable') 在工作区被改为『会话导航服务不可用（uiWorkspace 未注入）』，既丢失既有措辞『暂不可用』、又未覆盖本卡新增的 layout 缺失成因 → 本卡验收字面点名的『jumpResultMessage 既有断言』(tests/board-info-fixes.test.ts:307) 变红。归因：board-mount.ts 不在本卡 filesChanged（研发卡仅 session-jump.ts + test），属工作区既有未提交改动；但验收命令字面未满足。",
    "9) 【连带项·验收未达字面】全量验收命令 npx vitest run packages/web/dsh-pmboard/tests → 38 failed files / 165 failed tests (246 files)；其中本卡新用例 session-jump.test.ts 8/8 通过，失败主体为其它工作线既有红（client-view/execute-task/stage-prompts/gate-handlers 等）。『全绿（含 jumpResultMessage 既有断言）』字面不成立。",
    "10) 【连带项·部署侧】构建产物陈旧：lib/client.js(2026-09-28T20:05:35) 早于 session-jump.ts(20:08:59)，产物内 selectPanel/getPageLayout 0 命中、open-board 1 命中 ⇒ 线上 :13080 GUI 仍跑旧跳转逻辑，需 pnpm build:client + 页面重载才真正生效（联调卡已登记为遗留观察，交测试/部署卡）。",
    "11) 【范围外观察】footer-action.ts:21 仍导出 OPEN_EVENT 且 211/223 仍派发，但全仓 addEventListener 对 open-board/OPEN_EVENT 零命中、index.ts 已不再 import 该文件 ⇒ 空转死常量；属 FR-4/迁移清单范围，本卡未处理（符合卡面范围）。"
  ],
  "evidence": [
    "read packages/web/dsh-pmboard/src/client/session-jump.ts（1-259 行全文）：jumpToSession 顺序为 getUiWorkspace→getPageLayout→backToConversation()→openSession()；archived/missing 分支保留。",
    "grep -rn 'closeHostPanel' packages/web/dsh-pmboard/src → 0 命中（仅 tests 与文档注释保留说明）。",
    "cd packages/web/dsh-pmboard && npx vitest run tests/session-jump.test.ts --reporter=basic → Test Files 1 passed (1) / Tests 8 passed (8)，exit=0（含顺序、当前会话不重复 openSession、layout/uiWorkspace 不可用、archived/missing 保留、closeHostPanel 不再导出）。",
    "npx vitest run packages/web/dsh-pmboard/tests --reporter=basic（仓库根，验收字面命令）→ Test Files 38 failed | 205 passed | 3 skipped (246)；Tests 165 failed | 2421 passed | 20 skipped (2606)；明确点名项 tests/board-info-fixes.test.ts > jumpResultMessage 用例失败（断言 '暂不可用'）。",
    "git diff HEAD -- packages/web/dsh-pmboard/package.json → inject 数组由 ['slots','sessions','workspaces'] 改为 [...,'workspaces','layout']（仅 +layout）。",
    "read packages/web/dsh-pmboard/src/client/index.ts:26（inject 含 'layout'）、:62 setPageLayout(ctx.layout)、:83 clearPageLayout()；read page/page-runtime.ts（零 import，setPageLayout/getPageLayout/clearPageLayout）。",
    "grep -rn 'archivedSessionIds|handleSessionJump|jumpToSession|OPEN_EVENT' packages/web/dsh-pmboard/src → session-jump/handleSessionJump 调用点保留；footer-action.ts:21/211/223 仍派发 OPEN_EVENT 且无监听。",
    "read src/client/render/dom-utils.ts:93-110 → 归档 chip 仍含 data-action=\"jump-session\" + data-archived=\"true\"（可点）。",
    "stat -f '%Sm %N' lib/client.js src/client/session-jump.ts → 20:05:35 vs 20:08:59（产物早于源码）；grep -c selectPanel/getPageLayout/open-board lib/client.js → 0/0/1（产物为旧逻辑）。",
    "read docs/requirements/REQ-260928185112-e20d/design/architecture.md:162-171 + requirement.md:57-58（FR-3）+ tasks/t-bb1e62.md:18-19 与 queue.json:2229/2466（父卡实施方案）作为复核基准。"
  ]
}
