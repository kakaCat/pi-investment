---
requirement_refs: BUG-1, BUG-2
---

# 测试用例 · REQ-260922133212-dd5b

## 单测（tests/requirement-dir-pattern.test.ts） `serves: BUG-1`

TC-1 旧六位 hex 通过（REQ-f6307c / agent-dh 前缀变体）；TC-2 新时间戳通过（REQ-260922012924-2e29 / REQ-260922133212-dd5b，修复前必现 false）；TC-3 非法 id 拒（REQ-XYZ / 长度不足 / 缺 hex 段 / hex 超长 / 时间戳位数错误）；TC-4 目录层级错误与尾部多段拒。

## 实证（BUG-2） `serves: BUG-2`

TC-5 修复部署后 reqboard_submit(kind=archive) 对 REQ-260922012924-2e29 返回 success=true（修复前同调用 REQBOARD_INVALID_INPUT）；台账 archive.dir 非空。
