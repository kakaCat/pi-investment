# REQ-1bb221 实施计划 · 公告板「我来解决」动作路由统一到公共库（智能执行同款）

- 需求：REQ-1bb221（bug）
- 窗口：w-61022a21（角色 investor）
- 计划日期：2026-09-14（主体修复已上线并核验，本计划覆盖收口项）

## 1. 现象与根因（实证）

GUI 公告板点「我来解决」→ `POST /dashboard/api/bulletin/action` **稳定 500**：

```
HTTP 500 {"success":false,"error":"memory not found: 026cd6a3-0936-4721-85ae-620dc28355e3"}
（curl :13080 真实路径，2026-09-14 00:20）
```

根因：`packages/pages/bulletin/src/routes/bulletin-action-routes.ts`（224 行）**自写了一套 fetch**，打的是 Agent OS
**memory** 端点（RFC 009 前语义）。2026-09-08 RFC 014 把公告板迁到独立存储后，帖子只存在于 `board_posts`：

| 端点 | 结果 |
|------|------|
| `GET /api/v1/memory/<post-id>` | 404（旧语义，已失效） |
| `GET /api/v1/board/posts/<post-id>` | 200 |

即：**同一条业务动作存在两条实现，只有一条还活着**——公告板这条从头到尾没走统一实现（用户的判断成立）。

## 2. 修复（公共库化，对齐执行看板/持仓看板的「我来解决」）

| 文件 | 动作 |
|------|------|
| `packages/solve-kit/src/board-solve.ts` | **新增** 公共 handler `createBoardSolveHandler`：认领 → 投递目标窗口 → 消息带闭环指令（
| `packages/solve-kit/src/http.ts` / `target.ts` | **新增** 公共件：`json`/`readBody`（64KB 上限）与 `windowCode`/`deliverMessage`；`host.ts` 340 → 301 行并 re-export 保持兼容 |
| `packages/pages/bulletin/src/routes/bulletin-action-routes.ts` | 224 行 → **66 行适配器**，删除全部自写 fetch |
| `packages/pages/bulletin/package.json` | 增加 `@pi-investment/solve-kit`/`agent-os-client` 依赖 |

状态读写统一经 `BoardPort`，生产实现 = `@pi-investment/agent-os-client` 的 `BoardClient`（与
`board_post`/`board_read`/`board_update` 工具**同源**），状态机/权限/乐观锁由服务端强制。

## 3. 契约（客户端零改动即兼容）

- 成功：`200 {success:true,data:{post_id,action,status,claimed,assignee,revision,target,delivery,note}}`
- 可预期错误：`200 {success:false,error}`（缺参数/非法 action/帖子不存在/已终结/他人已认领/乐观锁冲突）
- 仅未预期异常：`500`（兜底）
- 客户端 `board-mount.ts:274` 读取的 `data.delivery.delivered` 与 `data.note` 字段名未变。

## 4. 已验证（线上，2026-09-14 00:36 CST）

1. 假 id → 200「帖子不存在或已删除」；真实 done 帖 → 200「该帖已终结」（只读，写前被拒）；缺 post_id / 非法 action → 200 可读错误（修复前一律 500）。
2. 端到端：一次性 open 帖 `65092759` → 真实 GUI 路径 → `200 success`，`open → claimed`、`assignee=investor`、`revision 1→2`、`delivery.delivered=true`、`target.window=w-61022a21`；服务端 moderation_log 落 claim；随后 drop 清理（claimed → dropped）。
3. 本地：分支矩阵 8/8 全 200；真连 :8080 只读探针 2/2；`tsc --strict` 零错；`relink-profile.py --check` 25/25。

## 5. 收口任务（本计划待拆项）

- **t1 回归测试固化**：把一次性 /tmp harness 变成 `packages/pages/bulletin` 的 vitest 用例，覆盖 8 个分支 + 信封契约 + handler 导出可解析。
- **t2 三看板一致性审计**：核对执行看板/持仓看板/公告板三处动作路由是否都只依赖公共库 handler，`grep` 确认无裸打 `/api/v1/memory` 的残留。
- **t3 文档归档**：`docs/work-logs/2026-09/req-1bb221-bulletin-solve-unify.md`（根因、契约、错误信封约定、已知限制）。
- **t4 转交语义评估**：服务端 `BoardStateMachine` **无 transfer 动作**，「转交」目前只写进 PATCH note（assignee 恒为实例身份）。评估是维持现状还是推进服务端改派，给出结论与影响面，不擅自改服务端。

## 6. 风险与回滚

- 风险：公告板与其它看板共用 handler 后，任一侧改动会同时影响三处 → t1 的契约测试即为护栏。
- 回滚：`git revert 4e7e3784`（wip 检查点），或把 bulletin 路由退回自写实现（不推荐——那正是本次 500 的来源）。
