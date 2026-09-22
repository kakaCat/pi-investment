---
requirement_refs: BUG-1
---

# 数据模型 · REQ-260922133212-dd5b

## 无数据模型变更 `serves: BUG-1`

本修复只改一个正则常量，不改任何存储结构。两种 id 格式：旧 `REQ-[0-9a-f]{6}`（六位 hex）、新 `REQ-\d{12}-[0-9a-f]{4}`（YYMMDDHHmmss + 4 位 hex，RandomIdFactory 真身）。存量台账两种 id 共存，校验端双兼容即完整覆盖。
