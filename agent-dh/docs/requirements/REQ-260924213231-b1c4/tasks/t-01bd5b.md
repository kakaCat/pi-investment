# t-01bd5b 投影逐份登记态到 reqboard_status·测试

> 子卡（父卡 t-7e9633 · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
投影逐份登记态到 reqboard_status·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-01bd5b-test.md，在 filesChanged 中列出该文件

## 实施方案
改 packages/web/dsh-pmboard/src/application/internal/design-docs.ts（designDocRegistration 合并磁盘/产物簿/确认章）、packages/web/dsh-pmboard/src/application/query/QueryState.ts、packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts（输出 schema 增 design_docs[]）；回归 packages/web/dsh-pmboard/tests/tools-status.test.ts。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-25 00:09:14（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-01bd5b-test.md
- 完成项：
  - 运行父卡 t-7e9633（T-4）目标命令：cd packages/web/dsh-pmboard && npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts —— 3 文件 / 35 用例全通过，退出码 0
  - 逐例核对（--reporter=verbose）：tools-status.test.ts 7 例（含 design_docs[] 逐份四态与磁盘+台账一致、front-matter sides/design_exempt、未绑定窗口空数组、未知 category 边界）、design-registration.test.ts 9 例（I-1 登记幂等/边界/path 语义/归属校验）、output-contract.test.ts 19 例（含 defineStatusTool 全 return 分支键已声明）全部 ✓
  - 记录被测基线 sha256 前 16 位（design-docs.ts 5748341840ef3886 / QueryState.ts e98306ee3fc42d50 / StatusTool.ts 43797d32d8c9311d 及三个测试文件），实现基线 = 工作区 HEAD 9e5ebf60 + 本需求未提交改动
  - 验收标准→用例对照表（三态一致性、行集顺序、front-matter 策略、回归面）写入测试记录
  - 未修改任何实现或测试源码，本轮新增产物仅 evidence/t-01bd5b-test.md（100 行）
- 执行段：1 次（末次 2026-09-25 00:07:35，outcome=succeeded）
