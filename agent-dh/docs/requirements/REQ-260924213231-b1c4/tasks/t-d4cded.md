# t-d4cded 打零参绑定 patch·研发

> 子卡（父卡 t-6cfab3 · 阶段 dev） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
打零参绑定 patch·研发

## 解决什么问题
子卡阶段：研发

## 得到什么结果（验收标准）
改动已落盘：本轮执行内把零参绑定守护测试写入 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts，并跑 `cd packages/web/dsh-pmboard && npx vitest run tests/zero-arg-binding.test.ts` 全绿（贴命令与输出摘要）；已有 patch 与 package.json 登记保持不变

## 实施方案
新增 patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch（lib/process.js 绑定工厂 value: (args = {})，唯一改动）+ 根 package.json pnpm.patchedDependencies；新增 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。

[子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 执行与完工记录
- workflow run：2026-09-24 23:25:43（stopReason=completed，产出非空=True）
- 改动文件：
  - packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts
- 完成项：
  - 新增零参绑定守护测试 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts：四层门禁——①根 package.json 仍登记 @deepseek-ai/dsh-ptc-runtime-node 的 pnpm.patchedDependencies；②patch 文件仍含 `value: (args = {}) => {`；③已安装产物 lib/process.js 真的带默认参数；④跨进程行为：子进程跑真实 process.js，程序零参调用绑定，断言宿主收到 call 帧且 args 预序编码严格等于 [{kind:'object',keys:[]}]，回包后 done.value 为 {got:'pong'}
  - 测试自包含：从测试文件向上按 pnpm.patchedDependencies 锚点定位仓库根，优先 .pnpm 提升层、回退虚拟店扫描定位已安装包；自带 uint32BE 长度前缀 + JSON 的帧通道实现，不引入新依赖
  - 已有 patch 与根 package.json 登记保持原样（本卡未改动这两处）
- 执行段：3 次（末次 2026-09-24 23:23:20，outcome=succeeded）
