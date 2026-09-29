# t-dcade9 拆除旧机制（属性显隐/互斥/壳）·测试

> 需求：REQ-260928185112-e20d · 父卡：t-d52858 · 阶段：implement/frontend · 子卡阶段：test · 状态：done

## 在做什么
拆除旧机制（属性显隐/互斥/壳）·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）

grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

## 实施方案
删除 packages/web/dsh-pmboard/src/client/board-shell.ts；改 src/client/dom.ts 删除 ACTIVE_ATTR、OTHER_ACTIVE_ATTRS、ACTIVATE_EVENT、conversationColumn；改 src/client/styles/base.ts 与 src/client/styles/panel.ts 删除全部 html[data-dsh-pm-active] 选择器；改 src/client/footer-action.ts 删除入口按钮职责（无剩余用途则整文件删除）。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 完工记录（物化自实施链 workflow run 的 lastReport）
- {"filesChanged":[],"completed":["目标命令①（父卡 t-d52858 验收·静态）：grep -rn \"data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT\" packages/web/dsh-pmboard/src → 零输出、exit=1，与父卡「零命中（grep 退出码 1）」逐字命中 ✅","目标命令②（父卡 t-d52858 验收·构建）：pnpm --filter dsh-pmboard build:client → BUILD_EXIT=0；[verify-client] OK bundle=302100 bytes, 关键符号齐全, styles.ts 括号配对（styles.ts 以 } 收尾、wrap 哨兵未触发）✅","设计表静态判据 2（无代码命中）：grep -rnE \"board-shell|createBoardShell|ACTIVE_ATTR|OTHER_ACTIVE_ATTRS|closeHostPanel\" src → 仅 1 处说明性注释（board-mount.ts:7），零代码命中 ✅","定向单测全绿：client-page-panel / client-page-register / host-panel / board-attach / session-jump → 5 files / 25 tests passed，exit 0 ✅","冒烟全绿：npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → 1 file / 21 tests passed，exit 0 ✅","全包回归与基线逐项一致（新增红 0）：pnpm --filter dsh-pmboard test → 33 failed | 210 passed | 3 skipped（246 files）/ 83 failed | 2503 passed | 20 skipped（2606 tests），与开工基线 t-351435 记载的「33 个文件 / 83 例失败」完全吻合；设计表「全绿」措辞与实测基线的口径脱节已在 t-351435 修正，非本卡引入。","拆除到位复核：board-shell.ts 与 footer-action.ts 均 git status 记 D 且 ls 报 No such file;dom.ts 无 ACTIVE_ATTR / OTHER_ACTIVE_ATTRS / ACTIVATE_EVENT / conversationColumn（grep exit=1）；html[data-dsh-pm-active] 仅剩 3 处说明性注释（styles.ts:7 / styles/base.ts:5 / styles/panel.ts:217），无任何 CSS 选择器仍以该属性为锚。","口径提示（沿用复核卡 t-bbf54d 结论，非本卡新增偏离）：设计表「grep data-dsh-pm-active … 零命中（退出码 1）」在 -E 口径下不字面成立（3 处注释）；本卡按父卡字面命令（无 -E）复现为零命中，且语义上属性与选择器已全部清除。","未跑 E2E Playwright（:13080）——属 t-351435「行为等价验证（含 E2E）」卡范围，且本仓未内置 playwright；本卡不越界。"],"evidence":["cd /Users/yunpeng/pi-investment/agent-dh && grep -rn \"data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT\" packages/web/dsh-pmboard/src → 无输出；exit=1（2026-09-28 20:30）","cd packages/web/dsh-pmboard && pnpm build:client → '✔ Build complete in 518ms'、'wrapped dsh-pmboard -> lib/client.js 282819 bytes'、'[verify-client] OK bundle=302100 bytes, 关键符号齐全, styles.ts 括号配对'；BUILD_EXIT=0","cd packages/web/dsh-pmboard && npx vitest run tests/client-page-panel.test.ts tests/client-page-register.test.ts tests/host-panel.test.ts tests/board-attach.test.ts tests/session-jump.test.ts → Test Files 5 passed (5) / Tests 25 passed (25) / exit 0","cd /Users/yunpeng/pi-investment/agent-dh && npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → Test Files 1 passed (1) / Tests 21 passed (21) / exit 0","cd packages/web/dsh-pmboard && pnpm test → Test Files 33 failed | 210 passed | 3 skipped (246)；Tests 83 failed | 2503 passed | 20 skipped (2606)；EXIT=1（= 开工基线，无新增红）","grep -rnE \"board-shell|createBoardShell|ACTIVE_ATTR|OTHER_ACTIVE_ATTRS|closeHostPanel\" packages/web/dsh-pmboard/src → 仅 board-mount.ts:7 一处注释，exit=0（无代码命中）","git status --porcelain -- packages/web/dsh-pmboard/src/client/board-shell.ts packages/web/dsh-pmboard/src/client/footer-action.ts → ' D …/board-shell.ts'、' D …/footer-action.ts'；ls 两路径均 No such file or directory","grep -nE \"ACTIVE_ATTR|OTHER_ACTIVE_ATTRS|ACTIVATE_EVENT|conversationColumn\" packages/web/dsh-pmboard/src/client/dom.ts → 无输出 exit=1；grep -rn \"html\\[data-dsh-pm-active\\]\" packages/web/dsh-pmboard/src → 3 处注释（styles.ts:7 / styles/base.ts:5 / styles/panel.ts:217），exit=0"]}
