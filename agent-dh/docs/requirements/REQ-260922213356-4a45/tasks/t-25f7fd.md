# t-25f7fd 补节点输入包地址节并锁两路径一致

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
补节点输入包地址节并锁两路径一致

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/template-address-injection.test.ts -t TC-11 绿；压缩开/关两路径地址段逐字相等且输入包文本含「## 本节点文档」并位于「## 需求文档」之后；故障注入「地址只挂 H3、不挂输入包」→ 该测试变红；npx vitest run tests/isolate-node-context.test.ts 绿。

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/application/internal/node-input-package.ts：NodeInputPackageInput 增 templateRoot 与 currentTask；在「## 需求文档」小节之后追加「## 本节点文档（模板地址 · 先读再动手）」小节（复用 renderAddressSection，空集不追加，保持改造前逐字节一致）。改 packages/web/dsh-pmboard/src/application/use-cases/IsolateNodeContext.ts：向 buildNodeInputPackage 传 templateRoot 与当前任务。补 packages/web/dsh-pmboard/tests/template-address-injection.test.ts 的 TC-11（压缩开/关两路径、系统段不可得时输入包仍带地址）。

## 上游产出摘要（dependsSummary）
- 实现非肯定项分流（H3 verdict / H4 不附纪律）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T15:26:08.101Z，窗口 session-2c955dd9-15b6-4cc5-8a0b-67ff978455aa）

压缩后地址不丢：节点边界把上下文换成"节点输入包"时，包里也带上了同一份模板地址与上游必读；压缩开/关两条路径拿到的地址段逐字一致，成本账单（charCount）也算上了它。

### 完成项

- 改 src/application/internal/node-input-package.ts：在「## 需求文档」小节之后追加「## 本节点文档（模板地址 · 先读再动手）」小节（复用 renderAddressSection；空集不追加、逐字节兼容）
- 改 IsolateNodeContext.ts / node-settlement.ts / index.ts：把绝对模板根与当前任务卡透传到输入包构造（开关关闭或缺根时不注入）
- 补 tests/template-address-injection.test.ts 的 TC-11：输入包地址段与系统段逐字一致、位于需求文档之后、系统段不可得时输入包仍带地址、空集不追加
- 修正 T-3 的类型边界：UpstreamSource 去索引签名，helper 入参改用 RequirementRecord（typecheck 绿）
- typecheck 绿；地址/注入/隔离/压缩 5 个测试文件共 79 例绿

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/node-input-package.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/IsolateNodeContext.ts`
- `packages/web/dsh-pmboard/src/application/internal/node-settlement.ts`
- `packages/web/dsh-pmboard/src/index.ts`
- `packages/web/dsh-pmboard/src/domain/template/types.ts`
- `packages/web/dsh-pmboard/src/adapters/CaptureHook.ts`
- `packages/web/dsh-pmboard/src/application/internal/capture-section.ts`
- `packages/web/dsh-pmboard/src/application/gate/handlers/h3-inject.ts`
- `packages/web/dsh-pmboard/tests/template-address-injection.test.ts`

### 下一步

T-6（t-527636）空集兼容回归 + 回退开关；依赖本卡。

---
