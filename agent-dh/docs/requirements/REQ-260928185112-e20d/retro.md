# 复盘 · REQ-260928185112-e20d（页面插件统一 main 插槽 · refactor）

> 时间：2026-09-28 · 窗口 w-7f4acab0 · 结论：验收 39/39 通过 → 已归档。

## 1. 做成了什么

- **看板（dsh-pmboard）样板迁移**：中央面板改走原生 `main` 插槽 + `sidebar.panellist` 条目，
  导航归位到 `ctx.layout.selectPanel(id | null)`；删除 `closeHostPanel()` 补丁、`board-shell.ts`
  状态机（open/close/toggle、互斥属性、`ACTIVATE_EVENT`、MutationObserver 兜底、外部点击关闭）
  与全部 `html[data-dsh-pm-active]` CSS 依赖。
- **FR-3 根因修掉**：点卡片窗口 chip 不切会话，根因是「面板不参与布局导航」而非 openSession 失效；
  修后 `selectPanel(null)` + `openSession(sid)` 两句即达，归档会话给明确原因。
- **标准 helper**：`registerPagePanel` 一次注册两端（`MainPanelId` 同源），返回幂等 disposer。
- **其余 4 页迁移清单**：execution / genome / holdings / bulletin 的入口 / 属性 / CSS / 工作量 / 风险五列齐。
- **规模**：7 张父卡 / 28 张子卡全 done；改动集中在 `packages/web/dsh-pmboard/`（其余包一行未改）。

## 2. 过程里的三个真问题（都已留痕）

1. **`reqboard_task_run` 抛无信息硬错误**（`value is not lossless JSON`）：早退路径不设 `dispatched`，
   工具壳 `out.dispatched === false` 漏过后走成功分支、返回 `job_id/run_id=undefined`，
   被 dsh-tools 的 lossless 校验整转成硬错误 → agent 只能反复重试猜。**已修**（早退显式
   `dispatched:false` + 人话 reason；判别式收紧为 `!== true` + 可检索 code），源码/dist/单测/线上实测齐备。
   教训：凡工具回执（含早退/降级）先自问「有没有 undefined」，错误必须可检索可读。
2. **自动实施链的三处契约缺口**（让验收被连拦 3 次）：workflow 路径不落子卡 `tasks/<id>.md`、
   子卡验收模板是写死的通用话术（不可照做）、不产出 accepting 覆盖度所需的 `covers` 标注。
   本轮以降级处置通过（物化卡文档 / 修订 21 张子卡验收 / 新建根 `test-cases.md`），
   根因与建议修复已上公告板（post `e4e3517f-cb40-4c0b-99d5-7ae105959bab`）。
3. **卡面验收与 FR 自相矛盾**：`t-c7f36f` 卡写 `grep ACTIVE_ATTR | wc -l = 5`，而 FR-4 要求拆除
   dsh-pmboard 自身 `ACTIVE_ATTR` → 必然 5→4。已按实报 4 并在清单 §0 写明口径，未粉饰。

## 3. 数据（可复核）

- `pnpm --filter dsh-pmboard build:client`：exit 0，`[verify-client] OK bundle=302532 bytes, 关键符号齐全, styles.ts 括号配对`。
- `npx vitest run packages/web/dsh-pmboard/tests/client-page-panel.test.ts`：6 passed。
- `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts`：21 passed。
- dsh-pmboard 全量：246 文件 / 2613 例 → **83 failed / 2510 passed / 20 skipped**；failed 数与开工基线一致（无新增红）。
- 静态：`data-dsh-pm-active` / `board-shell` / `ACTIVE_ATTR` / `closeHostPanel` 等零命中。
- E2E（:13080）：侧栏条目 `aria-current="page"`、主列渲染、点 chip → `activePanelId=null` + 会话切换。

## 4. 留给下一次的

- 落地公告板帖里的三条链条修复（子卡文档 / 可执行验收 / covers），否则下一个走自动链的需求仍会在验收卡三次。
- 按 `migration-checklist.md` 排期其余 4 页；`t-HLD`（账户持仓）建议最后做（「挂载不取数」契约有既有测试锁）。
- dsh-pmboard 全量 83 处既有失败是技术债基线，与本需求无关，但会持续淹没新红——建议单独立项清理。
