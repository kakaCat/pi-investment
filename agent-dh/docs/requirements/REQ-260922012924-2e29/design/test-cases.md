---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 测试用例 · REQ-260922012924-2e29

## FR-1 / FR-2 单测 `serves: FR-1, FR-2`

TC-1：capture-tool.test.ts 四问断言（题目数=4、id 顺序 name/category/difficulty/doc_location、缺项回落 defaultsUsed 含 doc_location、AC-7.2 端到端）。TC-2：artifact-path.test.ts 增 requirementDocPath 四分支——缺省逐字节一致 / docBasePath 含 <REQ> / 不含 <REQ> 自动追加 id 子目录 / docLinks.requirement 优先级最高。

## FR-3 实证 `serves: FR-3`

TC-3：nodeIsolationEnabled 单测已覆盖 config 优先级（node-gates.test.ts 现状）；实施侧人工验收 = 重启后启动日志含 `压缩开关 NODE_ISOLATION=true`，G0 门文档未落盘时 isolation-trace 见 H2 `skip(doc_not_ready)`。

## FR-4 / FR-5 单测 + 实证 `serves: FR-4, FR-5`

TC-4：stages 路由测试断言 state 含 workspaceRoot/homeDir；file-address 测试断言绝对路径地址构造（前导斜杠保留）。TC-5：capture-tool.test.ts 增三用例——rejected 分支写留痕 / 留痕写失败降级不阻断 / 前置检查命中近期拒绝不调 ask。TC-6 实证：工作区=dsh-pmboard 的会话看板打开需求文档链接成功。回归：`npx vitest run packages/web/dsh-pmboard` 全量绿。
