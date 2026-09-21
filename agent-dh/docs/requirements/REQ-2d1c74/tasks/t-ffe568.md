# t-ffe568 更新设计文档交付状态投影与看板呈现

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
更新设计文档交付状态投影与看板呈现

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
运行 `npx vitest run tests/stage-panel.test.ts tests/stage-detail.test.ts`；预期全绿。断言：host 投影含 frontend.md 的 conditional=frontend、豁免项含理由；stage-panel 渲染条件徽标/豁免理由/成组确认文案；不新增页面或路由。

## 实施方案（implementation）
修改 src/application/internal/design-docs.ts：基于 T-1 策略输出必交、条件必交、豁免项（conditional/exempted）。修改 src/application/query/QueryStageDetail.ts 与 src/http/routers/stages.ts：host 侧读取 requirement.md front-matter 并注入投影，client 不碰 fs。修改 src/client/stage-panel.ts：条件必交显示「条件」徽标，豁免项灰显并展示理由，kind=design 确认按钮文案写明「将确认全部 N 份设计文档」。更新 tests/stage-panel.test.ts / tests/stage-detail.test.ts。

## 上游产出摘要（dependsSummary）
- 定稿设计文档策略与闸门错误契约

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T05:57:51.090Z，窗口 session-a3d998e1-5a3b-4729-970c-9263dc64e132）

看板「设计」节点现在如实展示文档集的新规则：声明了 sides=frontend 的需求，frontend.md 会带「条件·frontend」徽标出现在应交清单里；声明豁免的文档灰显并展示豁免理由（不再被当成「未交缺口」）。「确认产物」按钮在设计阶段写明「确认产物（全部 N 份）」——用户一眼知道一次点击会给全部设计文档盖章，而不是只认第一份。策略来源与 G2 拦截门是同一份 front-matter 解析，页面上看到的缺口就是 G2 拦的缺口。

### 完成项

- design-docs.ts：designDocStatus 按策略投影（必交 ∪ 条件必交带 conditional 徽标；有效豁免保留在清单带 exempted=理由）；新增 designDocPolicyOf（host 侧读 requirement.md front-matter，client 不碰 fs）；头注「不参与任何闸门」作废说明
- QueryStageDetail.ts：AssembleContext 穿线 designDocPolicy（可选，缺省空策略行为不变）；queryStageDetail 读 front-matter 注入；assembleStageDetail/Overview 增可选 opts
- stages.ts：handleStageDetail/handleStageOverview 读 front-matter 注入策略（与 handleRequirementMarks 同款 FileDocRepository 构造）
- stage-panel.ts：条件必交渲染〔条件·端侧〕徽标；豁免项 data-exempted 灰显 + 「已豁免：理由」，不按未交渲染
- views/artifacts.ts：computeGateStatuses 与 renderConfirmButton 改 design 成组语义（任何一份无章即待确认；按钮「确认产物（全部 N 份）」+ 悬停成组说明）
- 新增断言：stage-detail 两条（assemble 策略注入 + 路由 front-matter 接线），stage-panel 两条（徽标/豁免渲染 + 成组按钮三态）
- 验收命令两文件 80 用例全绿；全量回归 134 文件 1637 用例全绿；无新增页面或路由

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/design-docs.ts`
- `packages/pages/dsh-pmboard/src/application/query/QueryStageDetail.ts`
- `packages/pages/dsh-pmboard/src/http/routers/stages.ts`
- `packages/pages/dsh-pmboard/src/client/stage-panel.ts`
- `packages/pages/dsh-pmboard/src/client/views/artifacts.ts`
- `packages/pages/dsh-pmboard/tests/stage-detail.test.ts`
- `packages/pages/dsh-pmboard/tests/stage-panel.test.ts`
- `packages/pages/dsh-pmboard/lib/client.js`

### 下一步

T-6（t-065810）：清理设计阶段过时提示词与工作流指南

---
