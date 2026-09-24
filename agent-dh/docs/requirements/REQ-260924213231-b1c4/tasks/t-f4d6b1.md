# t-f4d6b1 pm 弹框统一来源标志·联调

> 子卡（父卡 t-9f96a1 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
pm 弹框统一来源标志·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-f4d6b1-integrate.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/domain/text/pm-badge.ts（pmHeader）；改 packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts、packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts、packages/web/dsh-pmboard/src/application/internal/capture-mapping.ts、packages/web/dsh-pmboard/src/application/use-cases/HandleFailure.ts 四处 header 走 pmHeader；新增 packages/web/dsh-pmboard/tests/pm-question-badge.test.ts。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-25 01:46:47（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-f4d6b1-integrate.md
- 完成项：
  - 接口 I-7（AskQuestion.header 来源标志）联调通过：请求样例、期望响应、实际返回三者一致（14/14 MATCH）
  - 覆盖四处 pm 构造点：reqboard_ask_confirm（真工具）、reqboard_accept_sheet 逐项+最终归档（真工具）、立项四问 buildCaptureQuestions、失败处置 openFailurePopup，下发给宿主的 header 均以 '📋 PM · ' 开头
  - 对照验证宿主原生提问不经 pmHeader、不带前缀；题干正文不被注入标志
  - 目标测试 pm-question-badge.test.ts 7/7 绿；接口层回归 tools-dispatch.test.ts 4/4 绿（合跑 2 files / 11 tests 全绿，exit 0）
  - 联调走临时探针 tests/__probe-t-f4d6b1.test.ts（运行后已删除），未修改任何实现或测试源码
  - 联调记录已写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-f4d6b1-integrate.md
- 执行段：2 次（末次 2026-09-25 01:45:33，outcome=succeeded）
