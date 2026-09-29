# t-eed664 拆除旧机制（属性显隐/互斥/壳）·研发

> 需求：REQ-260928185112-e20d · 父卡：t-d52858 · 阶段：implement/frontend · 子卡阶段：dev · 状态：done

## 在做什么
拆除旧机制（属性显隐/互斥/壳）·研发

## 解决什么问题
子卡阶段：研发

## 得到什么结果（验收标准）

grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

## 实施方案
删除 packages/web/dsh-pmboard/src/client/board-shell.ts；改 src/client/dom.ts 删除 ACTIVE_ATTR、OTHER_ACTIVE_ATTRS、ACTIVATE_EVENT、conversationColumn；改 src/client/styles/base.ts 与 src/client/styles/panel.ts 删除全部 html[data-dsh-pm-active] 选择器；改 src/client/footer-action.ts 删除入口按钮职责（无剩余用途则整文件删除）。

[子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 完工记录（物化自实施链 workflow run 的 lastReport）
- {"completed":["删除 src/client/board-shell.ts（旧容器注入/互斥激活/外部点击关闭的页面壳）","删除 src/client/footer-action.ts（336 行 sidebar.footer.action 入口按钮组件）","src/client/dom.ts：移除 ACTIVATE_EVENT、CONVERSATION_COLUMN_SELECTOR、conversationColumn()、ACTIVE_ATTR、OTHER_ACTIVE_ATTRS","src/client/styles/base.ts：移除侧栏入口 .dsh-reqboard-foot 区段与全部 html[data-dsh-pm-active] 隐藏选择器；.dsh-pm-view 由 display:none 改常显 flex","src/client/styles/panel.ts：html[data-dsh-pm-active] 锚改为 [data-dsh-pm-view] 锚，不再依赖全局激活属性","src/client/styles.ts：注释同步（拼接结果不再与拆分前逐字节一致）","src/client/index.ts：停止注册 sidebar.footer.action 入口、移除 OPEN_EVENT 监听；dispose 收敛为 page 卸载 + clearPageLayout","src/client/board-mount.ts：删除 mountBoard（board-shell 命令式路径），仅保留 attachBoard(container) 宿主挂载","核验说明：上述改动已在工作区落盘（board-mount.ts 头注释署名本卡），本轮完成逐项核验 + 构建/测试证据补齐，未重复改动代码"],"evidence":["pnpm build:client（cd packages/web/dsh-pmboard）→ 退出码 0；输出 'wrapped dsh-pmboard -> lib/client.js 282819 bytes' 与 '[verify-client] OK  bundle=302100 bytes, 关键符号齐全, styles.ts 括号配对'","npx vitest run tests/board-attach.test.ts tests/client-page-panel.test.ts tests/client-page-register.test.ts tests/session-jump.test.ts → Test Files 4 passed (4)；Tests 22 passed (22)","ls src/client/board-shell.ts src/client/footer-action.ts → 两个路径均 'No such file or directory'（文件已删除）","grep -rn --include='*.ts' -E 'ACTIVE_ATTR|ACTIVATE_EVENT|conversationColumn|OTHER_ACTIVE|dsh-reqboard-foot' src tests → 0 命中；mountBoard 仅剩 board-mount.ts:7 历史注释","grep -c 旧符号 lib/client.js → dsh-panel-activate=0、dsh-reqboard-foot=0、ReqboardFooterAction=0、footer-action=0；data-dsh-pm-active 仅 1 处（panel.ts 内的 CSS 注释，非选择器）","基线核对：git worktree add --detach /tmp/pmhead-check HEAD 后跑 tests/client-view.test.ts → 1 failed/49 passed，archived-bar 失败在 HEAD 已存在；该文件另一失败（DAG L0）来自在制的 views/stage-detail.ts 迁移，与本卡无关（核验后 worktree 已移除）；本卡未引入新失败"]}

改动文件：
- `packages/web/dsh-pmboard/src/client/dom.ts`
- `packages/web/dsh-pmboard/src/client/styles/base.ts`
- `packages/web/dsh-pmboard/src/client/styles/panel.ts`
- `packages/web/dsh-pmboard/src/client/styles.ts`
- `packages/web/dsh-pmboard/src/client/index.ts`
- `packages/web/dsh-pmboard/src/client/board-mount.ts`
