# t-db23dc 打零参绑定 patch·联调

> 子卡（父卡 t-6cfab3 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
打零参绑定 patch·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-db23dc-integrate.md，在 filesChanged 中列出该文件

## 实施方案
新增 patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch（lib/process.js 绑定工厂 value: (args = {})，唯一改动）+ 根 package.json pnpm.patchedDependencies；新增 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-24 23:26:31（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-db23dc-integrate.md
- 完成项：
  - 接口 I-5（工具绑定层/FR-4）零参绑定联调：请求样例 `await tools.reqboard_status()`（零参）→ 期望响应「与显式 `{}` 完全一致、无 binding arguments must be lossless JSON」→ 实际返回逐字符相同，三方一致（JSON.stringify 相等=true、错误串包含=false）
  - 对照实测：零参与显式 `tools.reqboard_status({})` 返回值逐字符相同（deep-equal: true），键集合 board_link/bound/clause_receive_status/next_actions/note/open_count/open_requirements/unreceived_clauses/window_key
  - 目标命令 `npx vitest run tests/zero-arg-binding.test.ts` 全绿：1 file / 4 tests passed，exit 0（四例守护：登记 / patch 文件内容 / 已安装产物 / 跨进程 wire 帧 args=[{kind:'object',keys:[]}]+done 回包）
  - 补丁链路四层落地核验：根 package.json pnpm.patchedDependencies 登记、patch 文件存在（544B，唯一改动 lib/process.js 第952块 value: (args = {}) => {）、已安装产物 node_modules/.pnpm/node_modules/@deepseek-ai/dsh-ptc-runtime-node/lib/process.js:955 命中补丁后代码、本窗口 run_code 零参调用正常返回
  - 联调记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-db23dc-integrate.md（74 行），并已 present 为交付物
  - 未修改任何实现/补丁/测试源码，本卡新增产物仅该记录文件
- 执行段：1 次（末次 2026-09-24 23:25:43，outcome=succeeded）
