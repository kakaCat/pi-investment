---
requirement_refs: FR-2, FR-4, FR-5
---

# 接口设计 · REQ-260922012924-2e29

## requirementDocPath（改造，纯函数） `serves: FR-2`

签名不变：`(requirement: RequirementRecord | undefined) => string`。解析优先级：`docLinks.requirement` → `docBasePath` 拼接 → 缺省 `docs/requirements/<REQ>/`。拼接契约：`<REQ>` 全部替换为需求 id；docBasePath 无 `<REQ>` 时追加 `<id>/` 子目录（防碰撞）；尾斜杠归一；文件名恒 `requirement.md`。无错误码——纯函数不抛，无需求记录返回 ''。

## GET /dashboard/api/reqboard/state（增字段） `serves: FR-4`

响应 BoardState 增加 `workspaceRoot: string`（绝对路径无尾斜杠，取 deps.cwd ?? process.cwd()，本实例 = /Users/yunpeng/pi-investment/agent-dh）与 `homeDir: string`（os.homedir()）。旧客户端读不到即忽略，向后兼容；无新错误码。

## reqboard_capture（行为变更，schema 不变） `serves: FR-5`

前置检查新增第三条：同窗口 30 分钟内存在拒绝留痕 → 返回 `{ success:false, requirement_id:'', note:'用户已于 HH:MM 在弹框选择不立项…' }`，不调 questions.ask。留痕数据结构：`CaptureRejection = { windowKey: string; at: number; title?: string }`，ring buffer 上限 50 条原子写，TTL 由消费方按 30 分钟判定，不设主动清理。
