# t-fc102f 接线四个注入点并解析模板根

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接线四个注入点并解析模板根

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/template-address-injection.test.ts -t TC-9 绿（三/四处地址段逐字一致）；npx vitest run tests/prompt-injection-log.test.ts 绿且 charCount 为增强后长度；pnpm typecheck 绿；空集时既有基线逐字节不变。

## 实施方案（implementation）
新增 packages/web/dsh-pmboard/src/adapters/TemplateRoot.ts（resolveTemplateRoot(config,moduleDir)：配置绝对路径覆盖 > path.resolve(moduleDir,../templates)；非绝对/不可用返 undefined；node:path 仅在此）；改 packages/web/dsh-pmboard/src/application/internal/capture-section.ts（boundSectionText 在 resolved 入段与 injectionLog.record 前调 augmentResolvedPrompt，留痕用增强后的 charCount）、packages/web/dsh-pmboard/src/adapters/CaptureHook.ts（onStagePrompt 前 augment）、packages/web/dsh-pmboard/src/gate-wiring.ts 与 packages/web/dsh-pmboard/src/index.ts（PluginConfig 加 templateRoot?/addressSectionEnabled?（默认 true），组合根解析并下传）。templateRoot 不可用时整段不注入 + 留痕 address_section_disabled（不静默）。

## 上游产出摘要（dependsSummary）
- 实现地址解析与渲染纯函数

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T15:16:26.732Z，窗口 session-2c955dd9-15b6-4cc5-8a0b-67ff978455aa）

地址段真的进提示词了：窗口收到的阶段纪律后面会跟着「本节点要产出的模板绝对地址 + 开工前该先读的上游文档」；四处注入点（每回合系统段 / 闸门后置链 / 唤醒注入 / 节点输入包待 T-5）由同一个纯函数产出，口径不可能漂移；没有地址可给或开关关闭时文本与改造前逐字节相同。

### 完成项

- 新增 src/adapters/TemplateRoot.ts：resolveTemplateRoot（配置绝对路径优先，否则包根 ../templates）与 addressSectionEnabled（默认开）
- 改 src/index.ts：PluginConfig 加 templateRoot/addressSectionEnabled，组合根解析并下传；解析失败时响亮告警（address_section_disabled）
- 改 src/gate-wiring.ts：向闸门链（H3）与捕获引导段传递模板根/开关
- 改 src/application/internal/capture-section.ts（系统段）与 src/adapters/CaptureHook.ts（唤醒注入）：入段/投递前调 augmentResolvedPrompt，留痕 charCount 用增强值
- 改 src/application/gate/handlers/h3-inject.ts：取词后折入地址段（含当前任务卡）
- 新增 tests/template-address-injection.test.ts（TC-9）：系统段与 H3 的地址段逐字一致、含同一组绝对地址、空集与关开关时无地址段
- typecheck 绿；T-2/T-3 两个测试文件共 25 例全绿；既有 capture/h3/gate-handlers/prompt-injection-log 回归 78 例绿

### 改动文件

- `packages/web/dsh-pmboard/src/adapters/TemplateRoot.ts`
- `packages/web/dsh-pmboard/src/gate-wiring.ts`
- `packages/web/dsh-pmboard/src/index.ts`
- `packages/web/dsh-pmboard/src/application/internal/capture-section.ts`
- `packages/web/dsh-pmboard/src/application/gate/handlers/h3-inject.ts`
- `packages/web/dsh-pmboard/src/adapters/CaptureHook.ts`
- `packages/web/dsh-pmboard/src/domain/template/types.ts`
- `packages/web/dsh-pmboard/tests/template-address-injection.test.ts`

### 下一步

T-4（t-43e21b）H3 verdict 分流 + H4 非肯定不附纪律；依赖本卡。注意：dsh-pmboard 运行态从 dist/index.mjs 加载，T-1~T-3 的源码变更需 pnpm build + 重启才在活实例生效。

---
