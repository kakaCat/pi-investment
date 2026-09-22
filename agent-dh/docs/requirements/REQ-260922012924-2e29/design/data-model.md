---
requirement_refs: FR-2, FR-4, FR-5
---

# 数据模型 · REQ-260922012924-2e29

## 既有字段（零迁移） `serves: FR-2`

`RequirementRecord.docBasePath?: string`（protocol.ts:815 已存在）——文档基目录，可含 `<REQ>` 占位符，可有/无尾斜杠。老记录无此字段 → FR-2 缺省分支输出与现状逐字节一致，**无回填**。

## BoardState 增量字段 `serves: FR-4`

`workspaceRoot: string`（绝对 POSIX 路径，无尾斜杠）与 `homeDir: string`。运行时派生（进程 cwd / os.homedir），不落台账、客户端不持久化，每次 fetchState 随取随用。

## CaptureRejection 留痕文件（新增） `serves: FR-5`

`state/capture-rejections.json`：`[{ windowKey: string; at: number; title?: string }]`，上限 50 条 ring buffer，原子写（临时文件 + rename），损坏时按空集处理（降级为"无拒绝记录"，不阻断立项）。台账（dsh-reqboard.json）schema 不变。
