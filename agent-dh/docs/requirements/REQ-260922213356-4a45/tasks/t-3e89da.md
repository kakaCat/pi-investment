# t-3e89da 实现地址解析与渲染纯函数

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现地址解析与渲染纯函数

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/template-address.test.ts 绿；空集时 renderAddressSection 返回空串且 augmentResolvedPrompt 与入参引用相等；渲染出的每条地址被 read 实读成功（非空内容）；把 templateRoot 改成仓库根相对 templates 后 TC-12 变红。

## 实施方案（implementation）
新增 packages/web/dsh-pmboard/src/domain/template/resolve.ts（resolveNodeTemplates(stage,category) 按类型档在前/通用档在后的稳定顺序取表并去重；resolveUpstreamDocs(source,stage,currentTask?) 只从已登记 artifacts 与 cardDoc 取，取不到不列出）、packages/web/dsh-pmboard/src/domain/template/render.ts（renderAddressSection 按 interfaces.md I-3 逐字契约渲染；两清单皆空→空串；校验 templateRoot 绝对路径与 relPath 形态）、packages/web/dsh-pmboard/src/domain/template/index.ts barrel，以及 packages/web/dsh-pmboard/src/application/internal/injection-address.ts（augmentResolvedPrompt：空集 return resolved 同引用；非空 { ...resolved, text: text+\n\n+section, charCount }；fragmentIds/routeKey/hitLevel/trimmed 不变）。补 packages/web/dsh-pmboard/tests/template-address.test.ts 的 TC-1/2/3/7/8/12。

## 上游产出摘要（dependsSummary）
- 定义模板地址映射表与守护单测

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T15:14:33.240Z，窗口 session-2c955dd9-15b6-4cc5-8a0b-67ff978455aa）

地址解析/渲染/装配四个纯函数落地：给定节点与类型就能算出该产出哪些模板的绝对地址、开工前该先读哪些上游文档，并折进既有注入文本；没有地址可给时原样返回，注入文本逐字节不变。

### 完成项

- 新增 src/domain/template/resolve.ts：resolveNodeTemplates（查表+枚举收窄）与 resolveUpstreamDocs（按节点顺序取上游产物 + 当前任务卡，取不到不列）
- 新增 src/domain/template/render.ts：renderAddressSection 逐字渲染（空集返空串；相对 templateRoot 响亮抛错；relPath 形态护栏）
- 新增 src/domain/template/index.ts barrel；新增 src/application/internal/injection-address.ts（augmentResolvedPrompt：空集返原引用，非空折入 text 与 charCount）
- 扩展 tests/template-address.test.ts 至 22 例（TC-1/2/3/7/8/12：矩阵、上游必读、空集引用相等、真 read 成功、非法枚举/防穿越）
- 故障注入：把 render.ts 的绝对路径校验临时改为接受相对路径 → 该用例变红；已还原（22 例复绿）

### 改动文件

- `packages/web/dsh-pmboard/src/domain/template/resolve.ts`
- `packages/web/dsh-pmboard/src/domain/template/render.ts`
- `packages/web/dsh-pmboard/src/domain/template/index.ts`
- `packages/web/dsh-pmboard/src/domain/template/types.ts`
- `packages/web/dsh-pmboard/src/application/internal/injection-address.ts`
- `packages/web/dsh-pmboard/tests/template-address.test.ts`

### 下一步

T-3（t-fc102f）把 augmentResolvedPrompt 接到四个注入点并解析 templateRoot；依赖本卡。

---
