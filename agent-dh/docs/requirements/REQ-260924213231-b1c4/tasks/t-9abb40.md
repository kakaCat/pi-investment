# t-9abb40 打零参绑定 patch·复核

> 子卡（父卡 t-6cfab3 · 阶段 review） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
打零参绑定 patch·复核

## 解决什么问题
子卡阶段：复核

## 得到什么结果（验收标准）
复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-9abb40-review.md，在 filesChanged 中列出该文件

## 实施方案
新增 patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch（lib/process.js 绑定工厂 value: (args = {})，唯一改动）+ 根 package.json pnpm.patchedDependencies；新增 packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts。

[子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 执行与完工记录
- workflow run：2026-09-24 23:28:31（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-9abb40-review.md
- 完成项：
  - 逐条给出设计（FR-4 / I-5 / E-9 / TC-9 / T-7）与实现的对照结论：13 条全部「无偏离」并附依据；未修改任何实现/补丁/测试源码，本轮唯一新增产物为本复核记录
  - 独立复现接口 I-5：run_code 内 A=零参 tools.reqboard_status()、B=显式 {}，deepEqual=true、bindingErrorInZero=false、键集合一致 → 零参等价 {} 成立
  - 核验补丁最小性：patch 仅 1 个 hunk、1 对代码行（value: (args) => { → value: (args = {}) => {），唯一文件 lib/process.js
  - 核验登记链路：根 package.json:338 登记 patchedDependencies；pnpm-lock.yaml 含 patch 条目/patch_hash=ancxltpwmrosis3cqkonlvi6xu/patched: true；提升层与虚拟店副本均已打补丁，无未打补丁残留
  - 核验 patch 可逆性：在包目录 patch -p1 --dry-run -R 退出码 0，证明已安装产物恰为 patch 后像
  - 复核结论：无实现偏离；另单列 M-1（design/architecture.md:239 检测方式写成另一 runtime 包 dsh-code-runtime-worker-thread 的 decodeWorkerJson，被补丁包实际拒绝点为 snapshotPtcJsonValue，process.js:958/962）——文档级、无功能影响、不阻断
- 执行段：1 次（末次 2026-09-24 23:26:32，outcome=succeeded）
