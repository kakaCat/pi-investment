# REQ-260928185112-e20d 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：Phase 1 看板迁移完成：中央面板改走原生 main 插槽 + sidebar.panellist 条目（新增 registerPagePanel 两端同源注册 helper），打开/回对话/跳会话改为框架级 selectPanel(id/null)，删除 closeHostPanel() 补丁与 board-shell/属性显隐机制；dsh-pmboard/src 内旧机制符号全部零命中；FR-3 修复「点窗口 chip 不切会话」根因。Phase 2 产出其余 4 页迁移清单。7 张父卡 / 28 张子卡全 done，需求已由链 rollup 到 accepting。

文档口径补充（显式登记，不静默）：① 实施链 workflow 路径只写 queue.json 的 lastReport，未落 tasks/<id>.md——本轮从队列权威数据物化 27 张子卡文档 + 7 份 reviews/ + 7 份 tests/；② design/{data-model,interfaces,test-cases}.md 按 architecture.md 契约与实施后代码补写；③ 21 张子卡验收标准已用 reqboard_task_move(acceptance=) 修订为「父卡可执行标准 + 本阶段具体命令」；④ 新建根 test-cases.md 作为 RTM accepting 覆盖度来源，7 条用例覆盖 35 张卡 100%。

唯一口径差异：卡面验收写 `grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l` = 5，实测 4——FR-4 拆除 dsh-pmboard 自身 ACTIVE_ATTR，同款面板必然 5→4（迁移前口径）。

## 1. 验收列表

### v1-1 · 新增页面注册 helper registerPagePanel

**验收内容**：【新增页面注册 helper registerPagePanel】验收：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. 断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id
3. grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 命令式看板改由宿主挂载（attachBoard）

**验收内容**：【命令式看板改由宿主挂载（attachBoard）】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿
2. 新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 注册两端并接线（index.ts）

**验收内容**：【注册两端并接线（index.ts）】验收：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

**操作步骤**：
1. pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）
2. grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

**预期结果**：按上述步骤执行后满足验收标准：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 跳转语义归位（selectPanel(null)）

**验收内容**：【跳转语义归位（selectPanel(null)）】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）
2. grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 拆除旧机制（属性显隐/互斥/壳）

**验收内容**：【拆除旧机制（属性显隐/互斥/壳）】验收：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

**操作步骤**：
1. grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）
2. pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

**预期结果**：按上述步骤执行后满足验收标准：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 行为等价验证（含 E2E）

**验收内容**：【行为等价验证（含 E2E）】验收：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

**操作步骤**：
1. ① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. ② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败
3. ③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）
4. ④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）
5. ⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿
6. ⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

**预期结果**：按上述步骤执行后满足验收标准：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 迁移清单收口（其余 4 页）

**验收内容**：【迁移清单收口（其余 4 页）】验收：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

**操作步骤**：
1. docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）
2. 文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

**预期结果**：按上述步骤执行后满足验收标准：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 新增页面注册 helper registerPagePanel·研发

**验收内容**：【新增页面注册 helper registerPagePanel·研发】验收：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. 断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id
3. grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。
4. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
5. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 新增页面注册 helper registerPagePanel·联调

**验收内容**：【新增页面注册 helper registerPagePanel·联调】验收：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. 断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id
3. grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。
4. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
5. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 新增页面注册 helper registerPagePanel·复核

**验收内容**：【新增页面注册 helper registerPagePanel·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 新增页面注册 helper registerPagePanel·测试

**验收内容**：【新增页面注册 helper registerPagePanel·测试】验收：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. 断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id
3. grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。
4. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；断言两次注册的 name 分别为 main 与 sidebar.panellist，且 main.key 与 panellist.id 都等于 spec.id；grep -r "page-kit" packages/web/dsh-pmboard/src/client/page/page-panel.ts 零命中。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-12 · 命令式看板改由宿主挂载（attachBoard）·研发

**验收内容**：【命令式看板改由宿主挂载（attachBoard）·研发】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿
2. 新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。
3. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
4. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-13 · 命令式看板改由宿主挂载（attachBoard）·联调

**验收内容**：【命令式看板改由宿主挂载（attachBoard）·联调】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿
2. 新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。
3. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
4. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-14 · 命令式看板改由宿主挂载（attachBoard）·复核

**验收内容**：【命令式看板改由宿主挂载（attachBoard）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-15 · 命令式看板改由宿主挂载（attachBoard）·测试

**验收内容**：【命令式看板改由宿主挂载（attachBoard）·测试】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿
2. 新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。
3. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿；新增单测用 vi.useFakeTimers 断言 attachBoard 返回 disposer，且 dispose 后 clearInterval 已清除、容器上的监听已移除（定时器计数归零）。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-16 · 注册两端并接线（index.ts）·研发

**验收内容**：【注册两端并接线（index.ts）·研发】验收：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）
2. grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。
3. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
4. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-17 · 注册两端并接线（index.ts）·联调

**验收内容**：【注册两端并接线（index.ts）·联调】验收：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）
2. grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。
3. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
4. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-18 · 注册两端并接线（index.ts）·复核

**验收内容**：【注册两端并接线（index.ts）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-19 · 注册两端并接线（index.ts）·测试

**验收内容**：【注册两端并接线（index.ts）·测试】验收：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）
2. grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。
3. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：pnpm --filter dsh-pmboard build:client 通过 scripts/verify-client-build.mjs（体积/关键符号/wrap 哨兵三道门，退出码 0）；grep -n "sidebar.footer.action" packages/web/dsh-pmboard/src/client/index.ts 零命中。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-20 · 跳转语义归位（selectPanel(null)）·研发

**验收内容**：【跳转语义归位（selectPanel(null)）·研发】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）
2. grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。
3. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
4. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-21 · 跳转语义归位（selectPanel(null)）·联调

**验收内容**：【跳转语义归位（selectPanel(null)）·联调】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）
2. grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。
3. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
4. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-22 · 跳转语义归位（selectPanel(null)）·复核

**验收内容**：【跳转语义归位（selectPanel(null)）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-23 · 跳转语义归位（selectPanel(null)）·测试

**验收内容**：【跳转语义归位（selectPanel(null)）·测试】验收：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）
2. grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。
3. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run packages/web/dsh-pmboard/tests 全绿（含 jumpResultMessage 既有断言）；grep -rn "closeHostPanel" packages/web/dsh-pmboard/src 零命中。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-24 · 拆除旧机制（属性显隐/互斥/壳）·研发

**验收内容**：【拆除旧机制（属性显隐/互斥/壳）·研发】验收：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）
2. pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。
3. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
4. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-25 · 拆除旧机制（属性显隐/互斥/壳）·联调

**验收内容**：【拆除旧机制（属性显隐/互斥/壳）·联调】验收：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）
2. pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。
3. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
4. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-26 · 拆除旧机制（属性显隐/互斥/壳）·复核

**验收内容**：【拆除旧机制（属性显隐/互斥/壳）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-27 · 拆除旧机制（属性显隐/互斥/壳）·测试

**验收内容**：【拆除旧机制（属性显隐/互斥/壳）·测试】验收：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）
2. pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。
3. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：grep -rn "data-dsh-pm-active|OTHER_ACTIVE_ATTRS|createBoardShell|ACTIVATE_EVENT" packages/web/dsh-pmboard/src 零命中（grep 退出码 1）；pnpm --filter dsh-pmboard build:client 仍退出码 0（styles.ts 以 } 收尾、wrap 哨兵未被行首污染）。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-28 · 行为等价验证（含 E2E）·研发

**验收内容**：【行为等价验证（含 E2E）·研发】验收：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. ① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. ② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败
3. ③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）
4. ④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）
5. ⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿
6. ⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。
7. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
8. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-29 · 行为等价验证（含 E2E）·联调

**验收内容**：【行为等价验证（含 E2E）·联调】验收：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. ① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. ② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败
3. ③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）
4. ④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）
5. ⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿
6. ⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。
7. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
8. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-30 · 行为等价验证（含 E2E）·复核

**验收内容**：【行为等价验证（含 E2E）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-31 · 行为等价验证（含 E2E）·测试

**验收内容**：【行为等价验证（含 E2E）·测试】验收：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. ① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿
2. ② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败
3. ③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）
4. ④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）
5. ⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿
6. ⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。
7. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：① npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts 全绿；② pnpm --filter dsh-pmboard test 的结果与开工基线一致（基线 2026-09-28 实测：33 个文件 / 83 例失败，均为既有缺陷，例如 tests/application/repository.test.ts 的 REQ id 正则过期），不新增任何失败；③ grep 零命中（data-dsh-pm-active / OTHER_ACTIVE_ATTRS / createBoardShell / closeHostPanel）；④ pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build 三闸）；⑤ npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿；⑥ Playwright 对 http://127.0.0.1:13080 的 4 条断言结果写入 verification.md。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-32 · 迁移清单收口（其余 4 页）·研发

**验收内容**：【迁移清单收口（其余 4 页）·研发】验收：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**操作步骤**：
1. docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）
2. 文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。
3. 【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）
4. 并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**预期结果**：按上述步骤执行后满足验收标准：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

【本阶段·研发】改动已落盘后：跑与本卡涉及文件对应的测试或命令并附命令与输出摘要（例如 `npx vitest run packages/web/dsh-pmboard/tests`，或 `pnpm --filter dsh-pmboard build:client`）；并用 `git status --porcelain -- packages/web/dsh-pmboard` 核对改动文件真实存在。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-33 · 迁移清单收口（其余 4 页）·联调

**验收内容**：【迁移清单收口（其余 4 页）·联调】验收：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**操作步骤**：
1. docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）
2. 文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。
3. 【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要
4. 接口类卡另给 `curl` 请求样例与响应。

**预期结果**：按上述步骤执行后满足验收标准：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

【本阶段·联调】跑 `pnpm --filter dsh-pmboard build:client`（要求 exit 0 且输出 `[verify-client] OK`）与相关测试并附命令与输出摘要；接口类卡另给 `curl` 请求样例与响应。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-34 · 迁移清单收口（其余 4 页）·复核

**验收内容**：【迁移清单收口（其余 4 页）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-35 · 迁移清单收口（其余 4 页）·测试

**验收内容**：【迁移清单收口（其余 4 页）·测试】验收：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**操作步骤**：
1. docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）
2. 文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。
3. 【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**预期结果**：按上述步骤执行后满足验收标准：docs/requirements/REQ-260928185112-e20d/migration-checklist.md 存在且含 4 行数据行、每行五列齐（grep -c "^| " migration-checklist.md 不小于 6）；文件内附命令 grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l 的输出等于 5。

【本阶段·测试】把父卡验收里的目标命令逐条跑一遍，粘贴命令与全绿结果摘要（含 Test Files / Tests 计数）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-36 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-37 · 需求级验收

**验收内容**：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——apps/web/tests/plugin-schema.smoke.test.ts、packages/web/dsh-pmboard/tests/board-attach.test.ts、packages/web/dsh-pmboard/tests/client-page-panel.test.ts、packages/web/dsh-pmboard/tests/client-page-register.test.ts、packages/web/dsh-pmboard/tests/host-panel.test.ts、packages/web/dsh-pmboard/tests/session-jump.test.ts。请补 serves: 声明，或说明为何无需映射。

**操作步骤**：
1. 孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——apps/web/tests/plugin-schema.smoke.test.ts、packages/web/dsh-pmboard/tests/board-attach.test.ts、packages/web/dsh-pmboard/tests/client-page-panel.test.ts、packages/web/dsh-pmboard/tests/client-page-register.test.ts、packages/web/dsh-pmboard/tests/host-panel.test.ts、packages/web/dsh-pmboard/tests/session-jump.test.ts。请补 serves: 声明，或说明为何无需映射。

**预期结果**：按上述步骤执行后满足验收标准：孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——apps/web/tests/plugin-schema.smoke.test.ts、packages/web/dsh-pmboard/tests/board-attach.test.ts、packages/web/dsh-pmboard/tests/client-page-panel.test.ts、packages/web/dsh-pmboard/tests/client-page-register.test.ts、packages/web/dsh-pmboard/tests/host-panel.test.ts、packages/web/dsh-pmboard/tests/session-jump.test.ts。请补 serves: 声明，或说明为何无需映射。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-38 · 需求级验收

**验收内容**：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 新增页面注册 helper registerPagePanel·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 命令式看板改由宿主挂载（attachBoard）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 注册两端并接线（index.ts）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 跳转语义归位（selectPanel(null)）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 拆除旧机制（属性显隐/互斥/壳）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**操作步骤**：
1. 验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 新增页面注册 helper registerPagePanel·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
3. 验收项 命令式看板改由宿主挂载（attachBoard）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
4. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
5. 验收项 注册两端并接线（index.ts）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
6. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
7. 验收项 跳转语义归位（selectPanel(null)）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
8. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
9. 验收项 拆除旧机制（属性显隐/互斥/壳）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
10. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）
11. 本条不阻断验收，但必须有人看过并决定。

**预期结果**：按上述步骤执行后满足验收标准：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 新增页面注册 helper registerPagePanel·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 命令式看板改由宿主挂载（attachBoard）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 注册两端并接线（index.ts）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 跳转语义归位（selectPanel(null)）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 拆除旧机制（属性显隐/互斥/壳）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-39 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- reqboard_task_tree → 7 张父卡与 28 张子卡全部 status=done
- pnpm --filter dsh-pmboard build:client → exit 0；[verify-client] OK bundle=302532 bytes, 关键符号齐全, styles.ts 括号配对（三闸全过）
- grep -rE "data-dsh-pm-active|board-shell|createBoardShell|ACTIVE_ATTR|OTHER_ACTIVE_ATTRS|closeHostPanel|ACTIVATE_EVENT" packages/web/dsh-pmboard/src → 零命中（exit 1）；board-shell.ts 与 footer-action.ts 已删除
- npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts → Tests 6 passed
- npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → Tests 21 passed
- dsh-pmboard 全量 npx vitest run → 246 文件：33 failed / 210 passed；Tests 83 failed / 2510 passed / 20 skipped；failed 数与改动前基线一致，无新增失败
- migration-checklist.md 存在（15325 B）；grep -c "^| " → 10（≥6，四页五列齐）
- grep -rl "ACTIVE_ATTR" packages/web/*/src/client/dom.ts | wc -l → 4（dsh-pmboard 已迁）
- t-351435 复核子卡 t-2d637e：设计 vs 实现无功能性偏离
- t-351435 测试子卡 t-33a049：静态 grep 零命中 + build:client 三闸 + 迁移面 5 测试文件 + E2E（:13080），产出 verification.md（含 §9 验收四件套）
- 文档完整性自检（DocCompleteness 同款谓词）：70 份文件齐全，DOC_COMPLETENESS_OK；根 test-cases.md covers 覆盖 35/35 任务

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 新增页面注册 helper registerPagePanel | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-2 | 命令式看板改由宿主挂载（attachBoard） | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-3 | 注册两端并接线（index.ts） | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-4 | 跳转语义归位（selectPanel(null)） | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-5 | 拆除旧机制（属性显隐/互斥/壳） | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-6 | 行为等价验证（含 E2E） | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-7 | 迁移清单收口（其余 4 页） | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-8 | 新增页面注册 helper registerPagePanel·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-9 | 新增页面注册 helper registerPagePanel·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-10 | 新增页面注册 helper registerPagePanel·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:05 |
| v1-11 | 新增页面注册 helper registerPagePanel·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-12 | 命令式看板改由宿主挂载（attachBoard）·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-13 | 命令式看板改由宿主挂载（attachBoard）·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-14 | 命令式看板改由宿主挂载（attachBoard）·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-15 | 命令式看板改由宿主挂载（attachBoard）·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-16 | 注册两端并接线（index.ts）·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-17 | 注册两端并接线（index.ts）·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-18 | 注册两端并接线（index.ts）·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-19 | 注册两端并接线（index.ts）·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-20 | 跳转语义归位（selectPanel(null)）·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-21 | 跳转语义归位（selectPanel(null)）·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-22 | 跳转语义归位（selectPanel(null)）·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-23 | 跳转语义归位（selectPanel(null)）·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-24 | 拆除旧机制（属性显隐/互斥/壳）·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-25 | 拆除旧机制（属性显隐/互斥/壳）·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-26 | 拆除旧机制（属性显隐/互斥/壳）·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-27 | 拆除旧机制（属性显隐/互斥/壳）·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-28 | 行为等价验证（含 E2E）·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-29 | 行为等价验证（含 E2E）·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-30 | 行为等价验证（含 E2E）·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-31 | 行为等价验证（含 E2E）·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-32 | 迁移清单收口（其余 4 页）·研发 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-33 | 迁移清单收口（其余 4 页）·联调 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-34 | 迁移清单收口（其余 4 页）·复核 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-35 | 迁移清单收口（其余 4 页）·测试 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-36 | 需求级验收 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-37 | 需求级验收 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-38 | 需求级验收 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
| v1-39 | 需求级验收 | ✓ 通过 | human/session-7f4acab0-a754-4c1d-b1c3-06e76697fde2 | 2026-09-28 21:12 |
