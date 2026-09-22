---
requirement_refs: BUG-1, BUG-2
---

# 设计 · REQ-260922133212-dd5b 归档门禁兼容时间戳 id

## 复现 `serves: BUG-1`

最小重现：`reqboard_submit(kind=archive, dir='docs/requirements/REQ-260922012924-2e29', ...)` → REQBOARD_INVALID_INPUT「需求目录不符合约定」。或用例级：`REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-260922012924-2e29')` 返回 false（应为 true）。

## 根因 `serves: BUG-1`

`src/shared/protocol.ts:1319` 的 `REQUIREMENT_DIR_PATTERN = /(?:^|\/)docs\/requirements\/REQ-[0-9a-f]{6}$/` 写死旧六位 hex id。id 生成端 2026-09 已改时间戳格式（`REQ-<12/14位数字>-<6位hex>`，CHANGELOG-req-id-timestamp.md），校验端未同步。定位依据：报错文案逐字命中 protocol.ts:1330 的 bad() 调用。

## 修复方案 `serves: BUG-1`

正则改为 `/(?:^|\/)docs\/requirements\/REQ-(?:[0-9a-f]{6}|\d{12,14}-[0-9a-f]{6})$/`——新旧两格式都收，其余形态（非法 id、错误目录层级）仍拒。不改 id 生成器、不动归档其他校验项（必填文档/合并去向/索引条目）、不顺手重构（类型档纪律）。

## 回归测试落点 `serves: BUG-1, BUG-2`

新用例落 `tests/` 中 protocol 目录约定的既有测试文件（先查 migration.test.ts / acceptance-archive.test.ts 哪个断言 REQUIREMENT_DIR_PATTERN，就近增补；都无则新建 tests/requirement-dir-pattern.test.ts，文件头 `// serves: BUG-1`）：旧格式过 / 新格式过 / `REQ-XYZ` 拒 / 路径层级错误拒。BUG-2 实证：修复+重启后补交 REQ-260922012924-2e29 归档材料成功（其 archive 字段从空变为有值）。

## 验收口径 `serves: BUG-1, BUG-2`

①新增单测绿；②`vitest run packages/web/dsh-pmboard` 失败集与主干基线差集为空；③修复部署后补交归档材料返回 success，台账 `REQ-260922012924-2e29.archive` 字段非空。
