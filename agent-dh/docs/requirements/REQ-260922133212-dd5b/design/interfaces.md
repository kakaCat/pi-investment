---
requirement_refs: BUG-1, BUG-2
---

# 接口设计 · REQ-260922133212-dd5b

## REQUIREMENT_DIR_PATTERN（正则常量，值变更） `serves: BUG-1`

签名不变（导出常量）。值从 `/(?:^|\/)docs\/requirements\/REQ-[0-9a-f]{6}$/` 改为 `/(?:^|\/)docs\/requirements\/REQ-(?:[0-9a-f]{6}|\d{12}-[0-9a-f]{4})$/`。消费方 assertArchiveMaterials 的错误码/文案不变（REQBOARD_INVALID_INPUT→invalid_input 映射不变）。

## reqboard_submit(kind=archive)（行为变化，schema 不变） `serves: BUG-2`

入参/出参 schema 不变；行为变化 = 新格式 id 的 dir 从一律被拒变为按规则校验通过。无新错误码。
