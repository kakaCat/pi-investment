# 测试证据 · REQ-260922133212-dd5b

```
$ cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/requirement-dir-pattern.test.ts \
    packages/web/dsh-pmboard/tests/migration.test.ts packages/web/dsh-pmboard/tests/acceptance-archive.test.ts
Test Files  3 passed (3)
Tests  25 passed (25)          # 2026-09-22 14:32

$ ./scripts/restart-with-build.sh --build-only → dist 20/20 通过；grep 新正则命中 dist/index.mjs ×2
$ self_restart（检查点 agent-self/20260922-143649）→ 重启成功

$ reqboard_submit(kind=archive, requirement_id=REQ-260922012924-2e29, dir=docs/requirements/REQ-260922012924-2e29, ...)
→ success: true（修复前同调用：REQBOARD_INVALID_INPUT「需求目录不符合约定」）

$ 台账核验：REQ-260922012924-2e29.archive.dir=docs/requirements/REQ-260922012924-2e29，
  mergedInto=["docs/guides/reqboard-capture-troubleshooting.md"]，17 份文档全列入清单（warning 清零）

$ ./scripts/restart-with-build.sh --check → 退出码 0（27/27 symlink-ok）
```
