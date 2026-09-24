# t-57bfa5 组合根瘦身使尺寸门禁转绿·复核

> 子卡（父卡 t-800d53 · 阶段 review） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
组合根瘦身使尺寸门禁转绿·复核

## 解决什么问题
子卡阶段：复核

## 得到什么结果（验收标准）
复核结论逐条给出（设计与实现的偏离，无偏离时显式写「无偏离」及依据）；并把复核记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-57bfa5-review.md，在 filesChanged 中列出该文件

## 实施方案
把配置/路径纯函数与捕获根装配从 packages/web/dsh-pmboard/src/index.ts 抽到新增 packages/web/dsh-pmboard/src/plugin-config.ts 与 packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts；index.ts 再导出 dshHomePath/nodeIsolationEnabled 保兼容。

[子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 执行与完工记录
- workflow run：2026-09-25 02:02:15（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-57bfa5-review.md
- 完成项：
  - 复核 T-12（父卡 t-800d53「组合根瘦身使尺寸门禁转绿」）设计与实现的逐条偏离：R1–R11 全部「无偏离」并给出依据（D-2 + T-12 行 + architecture.md L225 + 任务卡验收），另列 O-1..O-5 观察项（公开面新增/新增导出类型/onTurnFinished 跨卡托管/新目录 src/wiring/ 已由计划授权/目标三测未直接单测 assembleCaptureHook）
  - 核对落点与命名：新增 src/plugin-config.ts（42 行，PluginConfig + dshHomePath + nodeIsolationEnabled，逐行等值含注释）与 src/wiring/pm-capture-root.ts（161 行，createCaptureRuntime + assembleCaptureHook），index.ts 无残留定义
  - 核对兼容再导出：index.ts:73 export { dshHomePath, nodeIsolationEnabled }，探针实测与 plugin-config 导出为同一函数对象
  - 核对行为零变更与尺寸门禁：目标三文件 60/60 绿、index.ts 357 行 ≤400、全量套件未新增失败（失败 7 例 ⊆ 基线 9 例）
  - 将复核记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-57bfa5-review.md（134 行）
- 执行段：1 次（末次 2026-09-25 01:58:46，outcome=succeeded）
