# 测试用例（REQ-260924002956-f37c）

## 新增/修改的测试

| 文件 | 用例 | 覆盖 |
|------|------|------|
| `tests/capture-tool.test.ts` | 拒绝路径只发 1 段 ask | AC1：第一段作答为「✖️ 不需要立项」时，`questions.ask` 只被调用 1 次，第二段从未下发 |
| `tests/capture-tool.test.ts` | 拒绝路径返回值与留痕 | AC3：`success:false` / `requirement_id:''` / `capture-rejections.json` 新增记录 |
| `tests/gate-aware-questions.test.ts` | 拒绝路径 G0 入队 0 次 | AC2：`GatePostChainPort.enqueue` 调用次数为 0 |
| `tests/gate-aware-questions.test.ts` | 肯定路径 G0 入队 1 次 | AC4：肯定路径回归，G0 恰好入队 1 次 |
| `tests/gate-handlers.test.ts` | 无 from 闸门负分支不输出"节点仍在" | AC5：消息不含 `节点仍在` |
| `tests/gate-handlers.test.ts` | 有 from 闸门负分支仍印"节点仍在 {from}" | 防御：防止把 H4 改反 |

## 执行结果

- 关键文件：`npx vitest run capture-tool gate-aware-questions gate-handlers` → 37/37 全绿
- 全量包：`npx vitest run packages/web/dsh-pmboard` → 1674 passed / 96 failed（96 failed 全部来自隔壁窗口在飞重构，非本次引入）
