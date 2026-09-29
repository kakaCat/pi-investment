# t-bbf54d 拆除旧机制（属性显隐/互斥/壳）·复核

> 需求：REQ-260928185112-e20d · 父卡：t-d52858 · 阶段：implement/frontend · 子卡阶段：review · 状态：done

## 在做什么
拆除旧机制（属性显隐/互斥/壳）·复核

## 解决什么问题
子卡阶段：复核

## 得到什么结果（验收标准）
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 实施方案
删除 packages/web/dsh-pmboard/src/client/board-shell.ts；改 src/client/dom.ts 删除 ACTIVE_ATTR、OTHER_ACTIVE_ATTRS、ACTIVATE_EVENT、conversationColumn；改 src/client/styles/base.ts 与 src/client/styles/panel.ts 删除全部 html[data-dsh-pm-active] 选择器；改 src/client/footer-action.ts 删除入口按钮职责（无剩余用途则整文件删除）。

[子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 完工记录（物化自实施链 workflow run 的 lastReport）
- {
  "filesChanged": [],
  "completed": [
    "复核结论（t-bbf54d · 拆除旧机制）：核心拆除动作全部到位、无功能偏离；发现 2 条不符合项（均不影响运行时行为）：偏离①旧机制残留死代码、口径②静态判据字面不成立。",
    "逐条-无偏离：src/client/board-shell.ts 已删除（git status 记 D，ls 报 No such file）；src/client/footer-action.ts 已删除（git status 记 D），全包无残留 import（仅 page/register.ts 注释提到旧槽名 sidebar.footer.action）。",
    "逐条-无偏离：src/client/dom.ts 已移除 ACTIVE_ATTR / OTHER_ACTIVE_ATTRS / ACTIVATE_EVENT / conversationColumn（并连带移除 CONVERSATION_COLUMN_SELECTOR），全包零代码命中；index.ts 同时清掉 OPEN_EVENT（零命中）。",
    "逐条-无偏离：src/client/styles/base.ts、src/client/styles/panel.ts 中 html[data-dsh-pm-active] 选择器全部消失——无任何 CSS 规则仍以该属性为锚（仅剩 3 处注释提及）。",
    "逐条-无偏离：src/client/index.ts 已停止 sidebar.footer.action 的 slots.inject/register 与入口 OPEN_EVENT 监听，改调 registerPmboardPage 并 setPageLayout；layout 注入双处到位（index.ts inject 数组含 'layout'、package.json dsh.client.inject 含 'layout'）——对齐 migration.md 文件级盘点「index.ts 加 layout inject」。",
    "逐条-无偏离：src/client/board-mount.ts 已删除旧命令式路径（mountBoard + board-shell 容器注入/互斥/外部点击），仅保留 attachBoard(container)，与 migration.md 第 3 步「board-mount.ts 导出 attachBoard；不再建 shell」一致；src/client/session-jump.ts 的 closeHostPanel 零命中。",
    "偏离①（旧机制残留死代码，无功能影响，建议清理）：styles/panel.ts:219 仍保留 `[data-dsh-pm-entry] .dsh-pm-board { min-height: 0; }`（第 216 行注释亦引用 data-dsh-pm-entry），dom.ts:8 仍导出 `ENTRY_SELECTOR = '[data-dsh-pm-entry]'` 且全仓零消费者。data-dsh-pm-entry 是已删除的 footer-action 入口按钮属性，现无人写入 → 该选择器永不匹配、该常量不可达。属实未满足 design/migration.md 第 5 步「删 styles/base.ts 与 styles/panel.ts 的属性选择器」与第 6 步「清死引用」的字面要求（该常量不在本卡 implementation 的枚举清单内，但落在 FR-4「旧机制清除」意图内）。",
    "偏离②（静态判据口径冲突，非功能偏离）：requirement.md 判据 4 与 design/migration.md §行为等价验证表首行均要求 `grep -r \"data-dsh-pm-active\" packages/web/dsh-pmboard/src` 零命中（退出码 1），实测 3 命中/退出码 0，全部是说明性注释（styles.ts:7、styles/base.ts:5、styles/panel.ts:217）；本卡「得到什么结果」所写的同款 grep 亦字面不成立。语义上属性与选择器均已移除故无功能偏离；二选一处理：删除这 3 处注释，或把口径统一为 design 表第二行的「无代码命中」措辞。",
    "验证证据-构建：cd packages/web/dsh-pmboard && pnpm build:client → 退出码 0，[verify-client] OK bundle=302100 bytes, 关键符号齐全, styles.ts 括号配对（wrap 哨兵未触发）。",
    "验证证据-测试：pnpm --filter dsh-pmboard test → Test Files 33 failed | 210 passed | 3 skipped；Tests 83 failed | 2503 passed（失败为既有缺陷，如 tests/application/repository.test.ts 的 REQ id 正则过期），与 t-351435 记载的开工基线「33 个文件 / 83 例失败」逐项吻合，本卡未新增失败。",
    "说明：design §行为等价验证表写 `pnpm --filter dsh-pmboard test` 期望「全绿」，与本仓实测基线（33/83 既有失败）不一致——属验证设计措辞与基线脱节，已在 t-351435 以基线口径修正，非本卡实现偏离。"
  ],
  "evidence": [
    "cd /Users/yunpeng/pi-investment/agent-dh && git status --porcelain -- packages/web/dsh-pmboard → ' D .../src/client/board-shell.ts'、' D .../src/client/footer-action.ts'（两个文件均已删除）；ls 两路径均报 No such file or directory",
    "grep -rnE \"data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT\" packages/web/dsh-pmboard/src → 仅 3 处注释命中（styles.ts:7 / styles/base.ts:5 / styles/panel.ts:217），exit=0（本卡声明的「零命中、退出码 1」未达成，但无任何代码/选择器命中）",
    "grep -r \"data-dsh-pm-active\" packages/web/dsh-pmboard/src → 同上 3 处注释、exit=0（design 静态判据 1 字面不成立）",
    "grep -rnE \"board-shell|createBoardShell|ACTIVE_ATTR|OTHER_ACTIVE_ATTRS|closeHostPanel\" packages/web/dsh-pmboard/src → 仅 board-mount.ts:7 一处注释；无代码命中（符合 design 表第二行「无代码命中」）",
    "grep -rn \"data-dsh-pm-entry\" packages/web/dsh-pmboard → dom.ts:8（ENTRY_SELECTOR 定义，零消费者）+ styles/panel.ts:216/219（CITE 与选择器 [data-dsh-pm-entry] .dsh-pm-board）；全仓无任何代码写入该属性",
    "grep -rnE \"OPEN_EVENT|mountBoard|closeHostPanel|createBoardController|sidebar.footer\" packages/web/dsh-pmboard/src → 全部零代码命中（mountBoard 仅 board-mount.ts:7 注释、sidebar.footer 仅 page/register.ts:7/15 注释）",
    "cd packages/web/dsh-pmboard && pnpm build:client → '✔ Build complete in 521ms'、'wrapped dsh-pmboard -> lib/client.js 282819 bytes'、'[verify-client] OK  bundle=302100 bytes, 关键符号齐全, styles.ts 括号配对'，exit=0",
    "cd packages/web/dsh-pmboard && pnpm test → 33 failed | 210 passed | 3 skipped (246 files)；83 failed | 2503 passed | 20 skipped (2606 tests)，与 t-351435 基线一致",
    "read docs/requirements/REQ-260928185112-e20d/design/migration.md（第 5/6 步与 §行为等价验证）、requirement.md（FR-4、判据 4）、tasks/t-d52858.md（本卡实施与结果声明）、tasks/t-351435.md（测试基线）"
  ]
}
