# t-a45bcd 组合根瘦身使尺寸门禁转绿·联调

> 子卡（父卡 t-800d53 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
组合根瘦身使尺寸门禁转绿·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a45bcd-integrate.md，在 filesChanged 中列出该文件

## 实施方案
把配置/路径纯函数与捕获根装配从 packages/web/dsh-pmboard/src/index.ts 抽到新增 packages/web/dsh-pmboard/src/plugin-config.ts 与 packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts；index.ts 再导出 dshHomePath/nodeIsolationEnabled 保兼容。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-25 01:58:45（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-a45bcd-integrate.md
- 完成项：
  - 接口联调通过（C1–C6 全 MATCH）：对 T-12 抽出的四类接口面各发真实调用并逐字段比对「请求样例/期望响应/实际返回」——I-A src/plugin-config.ts 的 dshHomePath（3 例：显式 config > env DSH_HOME > ~/.dsh）与 nodeIsolationEnabled（9 例真值表：显式 config > env 1/true/on/yes(含 trim+大写) > 默认 false），I-B src/index.ts 兼容再导出同一性（dshHomePath/nodeIsolationEnabled 与 plugin-config.ts 为同一函数对象），I-C src/wiring/pm-capture-root.ts 的 createCaptureRuntime（三张空 Map + AgentDeliverer；agents 不可得永不抛、就绪时 followup 载荷含 text 与 source.plugin=dsh-pmboard）与 assembleCaptureHook（订阅 session/event、返回解除订阅、真实 user/message 走完整判定链命中 pendingCapture），I-D apply() 组合根装配（15 工具 + reqboard:capture order 60 + /dashboard/api/reqboard 路由）
  - 临时探针 tests/__probe-ta45bcd.test.ts 7/7 绿（跑完即删，已确认无残留）
  - 父卡 T-12 目标门禁复跑：npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts = 3 文件 60/60 绿；wc -l src/index.ts = 357 ≤ 400（抽取前 434）
  - 联调记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-a45bcd-integrate.md（含 C1–C6 三方对照表、探针输出、门禁命令与输出摘要、结论与遗留）
- 执行段：1 次（末次 2026-09-25 01:57:27，outcome=succeeded）
