# t-f49d5b 实现父卡子卡链进度条·复核

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
实现父卡子卡链进度条·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/progress-bar.ts --noEmit && npx tsx demo/selftest.mjs`（退出码 0、末行「模块自测全绿」）作为实现侧证据；再逐条对照 design/architecture.md、design/interfaces.md、design/data-model.md，在复核结论里对每条偏离写明依据文件与行号。

## 汇报 1（2026-09-28T05:49:54.444Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【复核·链执行回填】实现父卡子卡链进度条·复核：【复核口径/基线】被测交付物 = docs/requirements/REQ-260928001915-f978/demo/progress-bar.ts（研发子卡 t-8a854a 产出，sha256=2133151b2fcafe09dc46dbd3bb3f766f79fdd760a2e300c97f188bd4d61a6b90，与联调卡 t-d284d3 记录逐字相同 ⇒ 复核期间未被改动）。设计基线 = requirement.md §FR-7(L81-85)+数据契约(L185-191)、design/interfaces.md §cardHtml 的 .card-chain 契约(L180-214)、design/test-cases.md TC-3(L40-55，含明文色值)、design/use-cases.md 场景5(L120-144)、design/architecture.md L167/L206、prototype.html chainHtml(L347-356)+CSS(L93-105)、template.html .card-chain CSS(L64-69)；计划基线 = decomposition.md t7(L124-133)、queue.json/t-d379c7 验收（tsc + grep 阶段关键字 ≥4 + fillText/数字格式）。本卡为结论族 review，未改动任何交付文件。

### 完成项

- 【复核口径/基线】被测交付物 = docs/requirements/REQ-260928001915-f978/demo/progress-bar.ts（研发子卡 t-8a854a 产出，sha256=2133151b2fcafe09dc46dbd3bb3f766f79fdd760a2e300c97f188bd4d61a6b90，与联调卡 t-d284d3 记录逐字相同 ⇒ 复核期间未被改动）。设计基线 = requirement.md §FR-7(L81-85)+数据契约(L185-191)、design/interfaces.md §cardHtml 的 .card-chain 契约(L180-214)、design/test-cases.md TC-3(L40-55，含明文色值)、design/use-cases.md 场景5(L120-144)、design/architecture.md L167/L206、prototype.html chainHtml(L347-356)+CSS(L93-…
- 【父卡验收命令全绿（2026-09-28 本机实测，R-013 标注）】① `npx tsc demo/progress-bar.ts --noEmit` → TSC_EXIT=0；并用同目录副本注入 `const __fault: number = "not a number"` 做负向对照 → demo/__neg-progress-bar.ts(165,7) error TS2322、EXIT=2，证明该门在做真实类型检查而非空跑（副本已删除，git status 无残留）。② `grep -c "'dev'\|'integrate'\|'review'\|'test'" demo/progress-bar.ts` → 6 行（≥4 达标）。③ `grep -c fillText` → 1（L137），进度文本经 progressText() 的 `done + '/' + total` 数字格式（L87-91），满足『含 fillText 与数字格式』。
- 【独立复核 27/27 全绿（不复用 demo selftest，自建探针 /tmp/progress-review-probe.mts + npx tsx）】① STAGE_ORDER 逐字 = ['dev','integrate','review','test']；② SEGMENT_COLOR = {on:#34c759, now:#0071e3, '':rgba(0,0,0,.12)} 与 TC-3 明文逐值一致；③ 6 状态映射：done→#34c759、todo/cancelled→rgba(0,0,0,.12)、in_progress/integrating/testing/in_review→#0071e3；④ progressText(TC-3 输入 1done+1in_progress+2todo)='1/4'；⑤ alignKids 乱序输入归位 dev,integrate,review,test，未知 stageKind(probe) 追加尾部且总数计入(1/3)；⑥ chainH…
- 【一键构建自测全绿】`python3 demo/build-demo.py` → [汇总] 103 通过 / 0 失败 + [6] 子卡链进度 8/8 ok（4 段归位/三态着色/文本/进行中变体/DOM-Canvas 同口径/中文名齐全）+ BUILD_EXIT=0；连续两次运行产物 demo/dag-card-types-demo.html 的 sha256 恒为 4b93d15e8e6c8311396aa160ba24f95f99c9a8cc9dadd205cb98f928e96282a1（幂等），progress-bar.ts 全程 sha256=2133151b…a6b90 不变。
- 【无偏离项（逐条，均有实测依据）】① 4 段固定阶段 dev→integrate→review→test 与 FR-7(L82)/use-cases(L144) 一致（STAGE_ORDER L19 + alignKids L97-108 乱序归位）；② 三态色值绿 #34c759 / 蓝 #0071e3 / 灰 rgba(0,0,0,.12) 与 TC-3(L47-49)、prototype CSS(L101-102) 逐字一致；③ 进度文本『已完成数/总数』与 FR-7(L84)、prototype chainHtml(L353) 一致（done 计数）；④ DOM 契约 .card-chain 结构与 interfaces.md(L205-211) 一致（<i class="on|now|">…<span>n/total</span>），class 序列与文本逐字符相符；⑤ 父卡底部位置符合 FR-7『父卡底部』/use-cases(L132)：card-renderer.ts:197-199 仅在…
- 【偏离 D1·计划签名与实现不一致 → 确认偏离，责任在计划文本，影响低】decomposition.md t7 验收(L132)写『调用 `renderProgressBar(parentTask, 10, 60, 188)`』（父卡对象 + 3 个位置参、无 ctx）；实现为 `renderProgressBar(ctx, kids, x, y, w)`（progress-bar.ts L111-117，5 参）。依据：queue.json 落库的父卡实际验收（tsc+grep+fillText）不含调用签名；实现与兄弟 Canvas 后端约定一致（card-renderer.ts L24-25 import、L196-199 传 ctx/kids/x/y/w）。影响低：仓内无按计划 4 参调用方；外部若照 decomposition 字面编码会失败。建议同步 decomposition/验收文本或加薄适配层。
- 【偏离 D2·状态→颜色映射比 prototype 宽 → 确认字面偏离，符合 FR-7 语义，无回归】prototype.html chainHtml(L350)为 done→on / in_progress→now / 其余→''（仅 in_progress 判蓝）；实现 IN_PROGRESS_STATUSES=['in_progress','integrating','testing','in_review']→蓝（progress-bar.ts L62/L68-72）。结论：相对 prototype 字面成立偏离，但对 FR-7『进行中（蓝色）/待开始（灰色）』语义更贴合（integrating/testing 即联调中/测试中），且把复核卡 t-c969a8 登记的『Canvas 判蓝、DOM 只认 in_progress 判灰』双后端分叉收敛为单一真源（segmentClass→SEGMENT_COLOR），属修复式偏离；todo/done 两端一致。遗留解释空间：in_review 的中文…
- 【偏离 D3·TC-3 期望文本与输入自相矛盾 → 确认偏离，责任在设计文档，实现正确】design/test-cases.md TC-3 输入(L42)为『1 done、1 in_progress、2 todo』，期望(L46)却是 `2/4`；实现输出 `1/4`（FR-7 L84『已完成数/总数』+ prototype L353 按 done 计数，实测两处一致）。结论：实现正确，TC-3 期望值属笔误；建议测试前修订 TC-3，否则测试卡按字面断言会误判红（use-cases 场景5 L136 的『2/4』未给输入，不构成对照）。
- 【偏离 D4·阶段中文名 review='复核' vs 需求写『评审』 → 确认字面偏离，纯展示层，影响低】requirement.md FR-7(L82)写『review（评审）』；实现 STAGE_LABEL.review='复核'（progress-bar.ts L22-39，仅出现在 DOM 段 title 提示）。stageKind 值仍为 'review'，class/文本/色值/几何不受影响；与本需求实际任务链命名（…·复核）一致，设计文档未规定阶段中文名。建议需求级统一口径（改需求文字或在设计登记 复核=review 阶段标签）。
- 【观察 O1·DOM <i> 增补 title 属性（低影响增量，非契约破坏）】chainHtml 输出 `<i class="on" title="研发：已完成">`（progress-bar.ts L150）；interfaces.md L205-211 与 prototype L347-356 的 <i> 无 title。class 序列/text 与契约逐字一致，建议在设计接口补记 title 约定，否则严格比对设计快照会判不一致。
- 【观察 O2·Canvas 与 DOM 几何不一致（低影响）】Canvas 段高 4px、段宽按可用宽度均分（progress-bar.ts L121-123/L129）；DOM 契约（template.html L66）为 14px×3px。两者颜色/文本/语义同源；Canvas 后端本身是 architecture.md L206 标注『本轮不做』的增量后端（复核卡 t-730c85 D4 已登记），不破坏设计契约，建议将来统一或明确 Canvas 为非契约渲染。
- 【观察 O3·FR-7『子卡折叠』子句不在本卡范围且未见实现（转验收阶段核对归属）】FR-7(L85)『子卡默认不在 DAG 中显示（或缩进显示）』；progress-bar.ts 只负责进度条渲染，实测 integration.ts/renderDagHtml 未过滤 role=child（子卡仍作独立节点渲染，d0 数据集 36 卡含 8 张子卡）。结论：非本卡实现偏离（本卡交付物边界=进度条），但该 FR-7 子句的归属需在设计/验收层裁定，建议验收阶段确认覆盖情况（prototype.html L276 裁定3 建议『子卡不单独成节点』，与现状不一致）。
- 【复核结论】FR-7 进度条核心契约（4 段顺序、三态配色、已完成数/总数文本、DOM .card-chain 结构、父卡底部渲染）与设计逐项一致，父卡三条验收命令全绿且经故障注入负向对照；独立探针 27/27、构建自测 103/0 全绿。4 处偏离中 D1/D3/D4 属计划或设计文档口径问题（D3 需测试前修订），D2 属语义合理且修复了既有双后端分叉的扩展；另有 3 项低影响观察。未发现功能性实现缺陷，复核通过。

---
