# RFC 009 实施状态

| 字段 | 值 |
|---|---|
| RFC | [009-board-lifecycle-management.md](../rfcs/009-board-lifecycle-management.md) |
| 状态 | 🟡 部分完成（W1/5 完成，30%） |
| 实施者 | agent-dh k3（W1）+ 待移交 |
| 更新时间 | 2026-08-25 |

---

## 实施进度总览

| 工单 | 状态 | 预估 | 实际 | 说明 |
|---|---|---|---|---|
| **W1** | ✅ 完成 | 0.5d | ~1h | Agent OS 后端路由 + 过滤 + 测试 |
| **W2** | ⏸️ 待实施 | 0.5d | - | GC 定时任务 |
| **W3** | ⏸️ 待实施 | 0.2d | - | agent-os-client TS 方法 |
| **W4** | ⏸️ 待实施 | 0.8d | - | lifecycle 插件工具 |
| **W5** | ⏸️ 待实施 | 0.3d | - | 端到端验收 A1-A20 |

---

## W1 已完成内容（commit b83e9eba）

### 后端 API 层（Go，Agent OS）

#### 1. Domain 类型（`internal/domain/memory_web.go`）

- ✅ `MemoryUpdateRequest`：支持 content 更新、metadata_patch、expected_revision 乐观锁
- ✅ `MemoryDeleteRequest`：软删原因记录
- ✅ `MemoryListRequest`/`MemorySearchRequest`：新增 `include_closed` 参数

#### 2. Repository 层（`internal/repository/memory_web_repository.go`）

- ✅ `Update()`：
  - 支持 content 更新
  - metadata patch 合并逻辑（先读后写）
  - **服务端 expected_revision 条件更新**（RFC 009 P1 修复：防 TOCTOU 竞态）
  - WHERE 子句：`id = $1 AND (metadata->>'revision')::int = $expected`
  - 0 行命中时区分"不存在"vs"revision 冲突"，返回 409
  
- ✅ `Delete()`：
  - 软删除：设置 `metadata.board_status = 'dropped'`
  - 记录 `drop_reason` 和 `closed_at`
  - 不硬删记录（硬删由 W2 GC 定时任务负责）

- ✅ `List()` / `Search()`：
  - 默认排除 `metadata->>'board_status' IN ('done', 'dropped', 'archived')`
  - `include_closed=true` 可查全部（供复盘/管理使用）

#### 3. Handler 层（`internal/api/memory_handler.go`）

- ✅ `Update()`：PATCH `/api/v1/memory/{id}`
  - 解析 MemoryUpdateRequest
  - 409 返回 revision conflict
  - 404 返回 not found
  
- ✅ `Delete()`：DELETE `/api/v1/memory/{id}`
  - Body 可选（reason 字段）
  - 软删成功返回 200

- ✅ `List()` / `Search()`：
  - 新增 `include_closed` 查询参数解析

#### 4. 路由注册（`internal/api/http_server.go`）

```go
api.HandleFunc("/memory/{id}", s.memoryHandler.Update).Methods("PATCH")
api.HandleFunc("/memory/{id}", s.memoryHandler.Delete).Methods("DELETE")
```

#### 5. 测试

- ✅ 更新 `MockMemoryWebRepository`（添加 Update/Delete 方法）
- ✅ 新增集成测试（`memory_handler_integration_test.go`）
  - `TestMemoryUpdate`：验证 PATCH 功能
  - `TestMemoryDelete`：验证 DELETE 功能
  - `TestMemoryListWithIncludeClosed`：验证过滤逻辑
- ✅ 所有测试通过：`go test ./internal/api/...`

### 编译验证

```bash
cd agent-os && go build -o /dev/null ./...  # ✅ 通过
```

---

## 待实施工作（移交清单）

### W2: GC 定时任务（0.5d）

**目标**：自动清理历史记录，避免数据库无限增长

**任务**：
1. 创建 `internal/service/memory_gc_service.go`
2. 实现两阶段 GC：
   - done/dropped 超 30 天 → archived
   - archived 超 180 天 → 硬删（DELETE FROM memories）
3. 定时任务：每日 04:00 运行
4. 集成到 Agent OS 启动流程（`cmd/server/main.go`）
5. 单测：模拟 GC 逻辑，验证 SQL 正确性

**SQL 示例**：
```sql
-- 阶段 1: done/dropped → archived（30天）
UPDATE memories
SET metadata = jsonb_set(metadata, '{board_status}', '"archived"')
WHERE metadata->>'board_status' IN ('done', 'dropped')
  AND (metadata->>'closed_at')::timestamp < NOW() - INTERVAL '30 days';

-- 阶段 2: archived → 硬删（180天）
DELETE FROM memories
WHERE metadata->>'board_status' = 'archived'
  AND (metadata->>'closed_at')::timestamp < NOW() - INTERVAL '180 days';
```

**注意事项**：
- GC 前记录日志（删除条数）
- 考虑分批删除（如单次最多 1000 条），避免长事务锁表
- 添加指标监控（可选）

---

### W3: agent-os-client（0.2d）

**目标**：TS client 支持新 API

**文件**：`agent-os-client/src/memory-client.ts`（或类似）

**任务**：
1. 添加方法：
   ```typescript
   async patchMemory(id: string, patch: {
     content?: string;
     metadataPatch?: Record<string, any>;
     expectedRevision?: number;
   }): Promise<Memory>
   
   async deleteMemory(id: string, reason?: string): Promise<void>
   ```

2. 更新 `listMemories()` / `searchMemories()` 签名：
   ```typescript
   async listMemories(options?: {
     category?: string;
     tag?: string;
     limit?: number;
     includeClosed?: boolean;  // 新增
   }): Promise<Memory[]>
   ```

3. 集成测试（可选，如果有测试框架）

---

### W4: lifecycle 插件（0.8d）

**目标**：实现 board_update / board_read / board_post 三个工具

**文件**：`agent-dh/packages/lifecycle/src/board-tools.ts`（新建）

#### 4.1 `board_update` 工具（核心，最复杂）

**参数**：
- `post_id: string` - 帖子 ID
- `action: "edit" | "claim" | "pause" | "blocked" | "complete" | "drop"`
- `note?: string` - 操作说明（closed 类动作必填）
- `title?: string` - 新标题（edit 用）
- `content?: string` - 新内容（edit 用）
- `expected_revision?: number` - 乐观锁
- `notify?: string[]` - 完成后通知的窗口列表（如 `["w-xxx"]`）

**执行逻辑**：
1. 读帖（`GET /api/v1/memory/{id}`）
2. revision 校验（如传）
3. 权限检查（作者/认领人/管理员，见 RFC §6）
4. 迁移合法性校验（状态机，见 RFC §3）
5. 构造 metadata_patch：
   - 更新 `status`、`status_reason`、`assignee`、`revision+1`
   - 追加 `moderation_log[]`
   - 设置时间戳（`claimed_at`、`closed_at`）
6. 调用 `client.patchMemory(id, { metadataPatch, expectedRevision })`
7. 如有 `notify`，调用 `window_message` 通知各窗口
8. 返回新状态

**幂等处理**：重复 complete/drop 同一帖 → 幂等成功，不重复写 log

**错误处理**：
- 409 revision conflict → 友好提示"帖子已被修改，请刷新后重试"
- 权限拒绝 → 明确提示"只有作者/认领人/管理员可执行此操作"
- 非法迁移 → 提示当前状态和允许的动作

#### 4.2 `board_read` 增强

**新增参数**：
- `status?: "active" | "done" | "dropped" | "all"` - 默认 active（open/claimed/blocked）
- `assignee?: string` - 按认领人过滤（如 `w-xxx`）

**输出增强**：每帖返回：
- `status` / `assignee` / `revision` / `claim_count` / `stale` / `age_hours`

**实现**：
- 调用 `client.listMemories({ tag: "office:board", includeClosed: ... })`
- 过滤 status / assignee
- 计算派生字段（stale / age_hours）

#### 4.3 `board_post` 微调

**新增参数**：
- `needs_action: boolean` - 默认 false
  - `true` → 初始状态 `open`（进悬赏池）
  - `false` → 初始状态 `done`（纯记录）

**实现**：
- 创建时在 metadata 设置 `{ status: needs_action ? 'open' : 'done', revision: 1, ... }`

#### 4.4 Schema 铁律

**每个 object 节点必须显式 `additionalProperties`**（见 `agent-dh/CLAUDE.md` Schema 铁律）

**冒烟测试**：
```bash
cd agent-dh && npx vitest run tests/plugin-schema.smoke.test.ts
```

---

### W5: 端到端验收（0.3d）

**目标**：验证 RFC 009 §9 的 A1-A20 验收标准

**前置条件**：
1. Agent OS 运行中（:8080）
2. DSH investment profile 运行中（:13080，加载 lifecycle 插件）
3. 数据库有测试数据（或手动创建）

**验收脚本**（建议用 TS/bash）：

```typescript
// A1: 作者 drop 自己的帖
const post = await boardPost({ title: "test", content: "test", needs_action: false });
await boardUpdate({ post_id: post.id, action: "drop", note: "测试删除" });
const list = await boardRead({ status: "active" });
assert(!list.find(p => p.id === post.id), "默认读不到 dropped 帖");
const allList = await boardRead({ status: "all" });
assert(allList.find(p => p.id === post.id)?.status === "dropped", "status=all 可查");

// A2: 非作者 drop 被拒
// （需要权限检查逻辑：读帖 metadata.author，与当前 window_id 比对）
// ... 18 条类似
```

**手动验收**（推荐）：
1. 创建测试帖：`board_post({ title: "删除测试", content: "...", needs_action: false })`
2. 执行各动作：edit / claim / pause / blocked / complete / drop
3. 检查状态变化、权限拒绝、乐观锁冲突
4. 确认通知发送、历史记录、过滤逻辑

**通过标准**：A1-A20 全部符合预期

---

## 技术债务与风险

### 已知限制

1. **Agent OS 无鉴权**（RFC §6）：权限仅在插件层强制，直连 :8080 可绕过
   - 当前单机可信环境可接受
   - 若开放网络访问必须加 OS 层鉴权

2. **status_reason 会被覆盖**（pause 覆盖 blocked 卡因）
   - 历史由 `moderation_log[]` 兜底
   - 明示取舍

3. **drop 不可逆**（除非 SQL 捞回）
   - 误删靠 180 天 GC 窗口内管理员介入
   - 不为低频事件设恢复按钮

### 实施注意事项

1. **Agent OS 是 legacy 服务**：改前确认它仍是公告板唯一后端
2. **重启走 `stop.sh`**：多实例环境下精确停止（见 `agent-dh/CLAUDE.md` §多实例铁律）
3. **插件 Schema 铁律**：每个 object 节点显式 `additionalProperties`，跑冒烟测试

---

## 下一步行动

### 立即（P0）

1. **决定实施者**：
   - 选项 A：移交给其他窗口（推荐，`assign_task` 或 `hire_window`）
   - 选项 B：k3 继续（需再投入 1.5 天）

2. **如果移交**：
   - 把本文档和 RFC 009 交给接手窗口
   - 确保对方理解 W1 已完成内容（可用 API）
   - 提供测试环境访问（Agent OS :8080、数据库连接）

### 短期（W2-W3，1 天内）

1. 实施 GC 定时任务（W2）
2. 实施 agent-os-client 方法（W3）
3. 验证后端层完整性（curl 测试 PATCH/DELETE）

### 中期（W4，2 天内）

1. 实施 lifecycle 插件三个工具
2. 本地冒烟测试（手动创建/删除帖子）
3. Schema 铁律验证

### 长期（W5，3 天内）

1. 端到端验收 A1-A20
2. 修复验收中发现的问题
3. 更新文档标记"✅ 已完成"

---

## 参考资料

- **RFC 009**：[docs/rfcs/009-board-lifecycle-management.md](../rfcs/009-board-lifecycle-management.md)
- **Commit**：b83e9eba（W1 实现）
- **Agent OS 代码**：`agent-os/internal/api/`, `agent-os/internal/repository/`
- **测试**：`agent-os/internal/api/memory_handler_integration_test.go`

---

**更新日志**：
- 2026-08-25：创建文档，记录 W1 完成状态，移交 W2-W5
