---
requirement_refs: BUG-1
---

# 架构设计 · REQ-260922133212-dd5b

## 改动点 `serves: BUG-1`

单点修改：`packages/web/dsh-pmboard/src/shared/protocol.ts` 的 `REQUIREMENT_DIR_PATTERN` 常量（目录约定校验的唯一事实源，被 assertArchiveMaterials 消费）。无新模块、无新依赖、无接口变更。

## 不动的地方 `serves: BUG-1`

id 生成器（RandomIdFactory）、归档其他校验项（必填文档/合并去向/索引）、台账 schema 一律不动（类型档：禁止顺手重构）。
