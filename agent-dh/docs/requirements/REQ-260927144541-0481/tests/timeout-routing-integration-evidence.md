# FR-6 超时归位联调证据（t-d80c2b）

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面（FR-6：任务/链级工具超时归位）
> 联调时点：2026-09-27（本地 vitest，工作区 `/Users/yunpeng/pi-investment/agent-dh`）
> 工具构造路径：`src/tools/index.js` 导出的真实 factory（`defineAdvanceTool` / `defineTaskExecuteTool` /
> `defineRunStatusTool` / `defineTaskStatusTool`），与线上组合根注册的是同一份源码。

## 一、结论

任务/链级的四个工具 `timeoutMs` 已全部路由到**非交互档**：投递类 → `LIMITS.timeoutWriteMs`（30_000ms），
查询类 → `LIMITS.timeoutReadMs`（15_000ms）；无一取 `LIMITS.timeoutInteractiveMs`（3_600_000ms）。
Dev 卡 t-59916c 只改了一行（`AdvanceTool.ts` 的 `timeoutInteractiveMs` → `timeoutWriteMs`），
其余三个工具此前已归位；别名 `reqboard_task_execute` 无独立值，随主入口同一 factory 继承。

## 二、请求样例 → 期望 → 实际

| # | 请求（样例） | 期望 | 实际（vitest 断言） |
|---|---|---|---|
| 1 | 构造 `reqboard_task_run` | `timeoutWriteMs` = 30_000 | ✅ 30_000 |
| 2 | 构造 `reqboard_task_execute`（别名） | 与主入口同值 30_000 | ✅ 30_000（深比较相等） |
| 3 | 构造 `reqboard_run_status` | `timeoutReadMs` = 15_000 | ✅ 15_000 |
| 4 | 构造 `reqboard_task_status` | `timeoutReadMs` = 15_000 | ✅ 15_000 |
| 5 | 四个工具并排扫描 | 任一 ≠ `timeoutInteractiveMs` 且 < 该值 | ✅ 过滤结果 `[]` |
| 6 | `reqboard_task_run({task_id:'t-p'})`，JobsPort 可用 | `success=true / status='dispatched' / job_id` 齐全，且立即返回（耗时 << 30s） | ✅ `job_id='job-integration-1'`、`run_id` 为字符串、台账 `req.autoRun=true`、耗时毫秒级 < 30_000 |

样例 6 是「30s 写档会不会掐断线上链」的正面回答：线上走**投递式路径**（认领 + `ctx.jobs.start` 后立即返回），
工具调用栈不持有整条链，因此写档绰绰有余；只有 `deps.jobs` 未装配的**内存测试/嵌入调用**同步兼容路径可能长跑——
该路径不代表线上（根因已由 DshJobsAdapter 接上 JobsPort 修复，见 tests/test-evidence.md §5.1/§5.3）。

## 三、FR-6 判定命令（requirement.md 原文口径）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
grep -rn "timeoutInteractiveMs" packages/web/dsh-pmboard/src/tools/AdvanceTool \
  packages/web/dsh-pmboard/src/tools/TaskExecuteTool \
  packages/web/dsh-pmboard/src/tools/RunStatusTool \
  packages/web/dsh-pmboard/src/tools/TaskStatusTool ; echo "exit=$?（应非 0）"
# → 无输出，exit=1 ✅
```

## 四、复现命令与结果

```bash
cd /Users/yunpeng/pi-investment/agent-dh
node_modules/.bin/vitest run \
  packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts \
  packages/web/dsh-pmboard/tests/task-run-contract.test.ts \
  packages/web/dsh-pmboard/tests/run-status-tool.test.ts \
  packages/web/dsh-pmboard/tests/task-status-ledger.test.ts \
  packages/web/dsh-pmboard/tests/tools-schema.test.ts \
  packages/web/dsh-pmboard/tests/output-contract.test.ts \
  packages/web/dsh-pmboard/tests/contract-shapes.test.ts \
  packages/web/dsh-pmboard/tests/task-tree.test.ts
# → Test Files 8 passed (8) / Tests 97 passed (97)，exit 0
```

新增联调用例 4 例在 `tests/timeout-routing-integration.test.ts`（TC-12a/b/c/d），其余 7 套为回归。

## 五、副作用核对

- 本卡只读工具对象属性 + 一遍真实 factory 构造；样例 6 的投递落在**内存 JobsPort/内存台账**，未产生真实后台任务。
- 未触碰运行中实例（未重启、未调用线上工具）；未写 `dsh-reqboard.json`、未改其它需求/任务数据。
- 未提交 git、未 `pnpm build`（遵循链纪律）。

## 六、遗留（交复核子卡 t-fc43f2 判）

- 同步兼容路径（内存测试/嵌入调用）仍可能跑过 30s 而被写档掐断。这是 FR-6 明示取非交互档后的已知取舍，
  不是回归；是否为其加档位说明/独立常量，交 review 与人工裁决。
