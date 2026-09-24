# 测试证据（REQ-260924002956-f37c）

## 关键回归测试

```
$ npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts packages/web/dsh-pmboard/tests/gate-handlers.test.ts

✓ packages/web/dsh-pmboard/tests/gate-handlers.test.ts  (11 tests) 4ms
✓ packages/web/dsh-pmboard/tests/gate-aware-questions.test.ts  (10 tests) 6ms
✓ packages/web/dsh-pmboard/tests/capture-tool.test.ts  (16 tests) 61ms

Test Files  3 passed (3)
Tests  37 passed (37)
```

## 全量包测试

```
$ npx vitest run packages/web/dsh-pmboard

Test Files  13 failed | 134 passed (147)
Tests  96 failed | 1674 passed (1770)
```

> 96 failed 全部来自隔壁窗口在飞重构（tsc/尺寸/层边界/地址段），本次范围内 6 文件 87 条测试全绿。详见 t-ec02a7 汇报。

## 真机验证证据

- `state/capture-rejections.json` 新增记录：`session-4c0d1035` at=`1790215994105`（2026-09-24 10:13:14 CST），晚于重启时刻 00:42:28
- diag log 中无「闸门待改进 / G0 未通过 / 节点仍在 brainstorming」投递
