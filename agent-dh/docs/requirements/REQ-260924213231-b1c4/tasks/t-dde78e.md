# t-dde78e 分化 G2 闸门文案并统一拒绝信封·联调

> 子卡（父卡 t-954348 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
分化 G2 闸门文案并统一拒绝信封·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-dde78e-integrate.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/application/internal/gate-feedback.ts（envelope）；改 packages/web/dsh-pmboard/src/application/internal/design-gates.ts（art===undefined/confirmedAt===undefined 分叉文案）、packages/web/dsh-pmboard/src/application/internal/content-gate-wiring.ts（message 统一走 envelope，判定不动）、packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts（已确认早返回补 gate_failure）；新增/改 packages/web/dsh-pmboard/tests/design-gate-messages.test.ts、packages/web/dsh-pmboard/tests/gate-feedback-envelope.test.ts、packages/web/dsh-pmboard/tests/design-completeness-gate.test.ts。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-25 00:26:36（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-dde78e-integrate.md
- 完成项：
  - 完成 I-9（拒绝信封：envelope / checkDesignCompletenessGate 未登记·待确认分叉 / reqboard_move 真工具路径）与 I-3（reqboard_ask_confirm 已确认早返回补 gate_failure）的接口联调，5 个用例逐例给出请求样例 / 期望响应 / 实际返回并判定 5/5 MATCH
  - 核对两种病因两种话：同一 code=design_doc_incomplete 下，未登记消息含「未登记」+ reqboard_submit(kind=design)，待确认消息含「待确认」+ reqboard_ask_confirm(target=artifact, kind=design)，两串不相同；两类 message 均含 —— 与 补齐：且 how 命中可执行锚点
  - 确认 code/gaps 结构与 kind 字段未因改文案而变化（护栏强度不降）
  - 把联调记录（三方对照 + 命令与输出摘要 + 结论）写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-dde78e-integrate.md
  - 清理临时探针 tests/__probe-tdde78e.test.ts（rm -f 并复核不存在）；未修改任何实现或测试源码，本轮新增产物仅证据文件
- 执行段：2 次（末次 2026-09-25 00:24:09，outcome=succeeded）
