# t-e80e8b 设计提示词写明登记命令·联调

> 子卡（父卡 t-216224 · 阶段 integrate） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
设计提示词写明登记命令·联调

## 解决什么问题
子卡阶段：联调

## 得到什么结果（验收标准）
接口联调通过：给出请求样例、期望响应与实际返回，三者一致；并把联调记录（命令与输出摘要）在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e80e8b-integrate.md，在 filesChanged 中列出该文件

## 实施方案
改 packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md 与 packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md（覆盖条目 1 写明登记命令+触发者+不要猜 kind），重跑生成器刷新 packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts；新增 packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts。

[子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 执行与完工记录
- workflow run：2026-09-25 00:56:57（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-e80e8b-integrate.md
- 完成项：
  - 从真实生成产物解析设计阶段提示词（light/heavy × 6 类型档共 12 档），抽出登记命令 reqboard_submit(kind=design)，与 reqboard_submit 工具 kind 枚举/execute 契约逐档对齐，判定请求样例、期望响应、实际返回三者一致（12/12 MATCH）
  - 真实执行验证正向路径：{kind:'design'} 首登 5 份 registered_count=5、design_docs 5×{on_disk:true,registered:true,confirmed:false}，台账新增 5 条 kind=design
  - 验证幂等：二次调用 registered_count=0、success=true、台账仍 5 条
  - 验证「不要猜 kind」可证伪：kind=designs 被绑定层枚举挡下（must be one of [...design...]），伪路径仍被 REQBOARD_ARTIFACT_NOT_OPENABLE 拒
  - 生成器同步门禁 check-prompt-fragments.mjs 退出 0；父卡验收测试 design-prompt-registration + prompt-baseline 2 文件 25/25 绿
  - 联调记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e80e8b-integrate.md，临时探针跑完即删（复核不存在），未改动任何实现/生成器/测试源码
- 执行段：2 次（末次 2026-09-25 00:54:33，outcome=succeeded）
