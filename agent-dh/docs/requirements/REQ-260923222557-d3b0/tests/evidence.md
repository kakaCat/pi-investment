# REQ-260923222557-d3b0 测试证据

> 采集时点：2026-09-24 00:05 ~ 00:10（本机 :13080 实例，工作区 /Users/yunpeng/pi-investment/agent-dh）
> 采集窗口：w-959cebfe（session-959cebfe-094f-4f09-894d-20a5c35d4d62）

## 1. 单元/集成用例（vitest）

```
cd packages/web/dsh-pmboard
npx vitest run tests/stage-panel.test.ts tests/node-panel.test.ts \
  tests/concurrency-limits.test.ts tests/worktree-injection.test.ts tests/worktree-events.test.ts
```

结果（exit 0）：

```
 ✓ tests/worktree-events.test.ts (5 tests) 2ms
 ✓ tests/node-panel.test.ts (27 tests) 6ms
 ✓ tests/stage-panel.test.ts (54 tests) 33ms
 ✓ tests/concurrency-limits.test.ts (8 tests) 18ms
 ✓ tests/worktree-injection.test.ts (5 tests) 5ms

 Test Files  5 passed (5)
      Tests  99 passed (99)
```

覆盖关系：TC-1..TC-5（FR-8/FR-10 取词与状态词）、TC-6/TC-7（FR-9 可点/占位）、TC-8（FR-5/6/7 常量锁定 + 旧值扫描）、FR-1..FR-4（worktree 文本与两条事件投递，含投递失败不阻断转移的故障注入）。

## 2. 构建门禁（客户端产物）

```
cd packages/web/dsh-pmboard && pnpm build:client
```

结果（exit 0，末行）：

```
wrapped dsh-pmboard -> lib/client.js 266247 bytes
[verify-client] OK  bundle=285229 bytes, 关键符号齐全, styles.ts 括号配对
```

确定性复核：连跑两次 `md5 -q lib/client.js` → 均为 `4c2ed0fc7ebf6bcb28ceb3e89441db9e`（产物可重现，且与 23:58 那份字节相同）。
产物关键串抽查（`lib/client.js`）：`未开始`、`拆分计划：decomposition.md（未交）`、`data-action="open-doc"`、`dsh-pm-np-head-state` 全部命中。

## 3. 线上核验（真实载荷 × 真实渲染器）

数据源：`GET http://127.0.0.1:13080/dashboard/api/reqboard/requirements/<id>/stage/design`（2026-09-24 00:0x 实时返回，HTTP 200）。
渲染器：`src/client/stage-panel.ts` / `src/client/node-panel.ts` 源码经 tsx 直跑（非 mock）。

| 项 | 观测 | 结论 |
|---|---|---|
| FR-8 旧管线 | 9 个 design 有 plan 记录的需求全走计划文案（REQ-47939a=「计划已批准」） | 文案不变 |
| FR-8 新管线 | 19 个走「设计文档 n/N 已交 / 设计已确认 / 待提交设计文档」 | 口径一致 |
| FR-8 口径不一致 | 0 条（全量 30 需求） | 通过 |
| FR-8 本需求 | design 头部=「设计已确认」 | 通过 |
| FR-9 已交 | 本需求 5 份设计文档全部渲染为 `data-action="open-doc"` 行，未交占位 0 条 | 通过 |
| FR-9 未交 | REQ-ac5282（design 阶段）预览拆分节点 → 「⬜ 拆分计划：decomposition.md（未交）」且不可点 | 通过 |
| FR-10 未到达 | REQ-ac5282 预览拆分、本需求预览验收 → 状态胶囊 `data-state="pending"`「未开始」 | 通过 |
| FR-10 已到达 | 本需求 设计=已设计、拆分=已拆分 | 通过 |

## 4. 部署与运行时

- `python3 scripts/relink-profile.py --check` → exit 0，`symlink-ok=3`（无副本漂移）。
- `:13080` 进程 PID 98527，启动 `Wed Sep 23 23:59:23 2026`（quick_restart，理由见 `.dsh-data/state/quick-restart-request.json`），晚于 `src/domain/limits.ts` 改动 23:47:03 → 宿主侧新值已加载。

## 5. 未覆盖项（诚实列出）

- **FR-5 运行期"弹框跨过旧 600 秒仍有效"未取得实测**：本会话为 PTC(run_code) 模式，其预算 default 120000ms / cap 600000ms 覆盖嵌套工具等待，10 分钟即上限，无法在一次调用内跨过旧值。详见 `reviews/self-review.md` §3。
- **无浏览器端 E2E**：本轮以"线上 API 载荷 + 源码渲染器"替代浏览器截图；面板交互（点击打开右侧栏）只验证到 HTML 属性（`data-action="open-doc"`）层面，未做浏览器点击回归。
