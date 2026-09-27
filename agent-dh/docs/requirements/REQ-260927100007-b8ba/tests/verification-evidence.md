# REQ-260927100007-b8ba 测试证据（命令 + 输出摘要）

> 全部命令在 `/Users/yunpeng/pi-investment/agent-dh` 下执行；输出为**粘贴的原始摘要**（非转述）。
> 生成时间：2026-09-27（implementing/accepting 节点）。

## T1 · 主验收批（21 文件 / 219 用例，全绿）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
node_modules/.bin/vitest run \
  packages/web/dsh-pmboard/tests/execute-task.test.ts \
  packages/web/dsh-pmboard/tests/lazy-expand.test.ts \
  packages/web/dsh-pmboard/tests/concurrency-limits.test.ts \
  packages/web/dsh-pmboard/tests/application/use-cases.test.ts \
  packages/web/dsh-pmboard/tests/tools-schema.test.ts \
  packages/web/dsh-pmboard/tests/apply-wiring.test.ts \
  packages/web/dsh-pmboard/tests/task-transition-guard.test.ts \
  packages/web/dsh-pmboard/tests/confirm-settle-plan-persist.test.ts \
  packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts \
  packages/web/dsh-pmboard/tests/status-lossless.test.ts \
  packages/web/dsh-pmboard/tests/advance-task-completeness-guard.test.ts \
  packages/web/dsh-pmboard/tests/contract-shapes.test.ts \
  packages/web/dsh-pmboard/tests/confirm-evidence.test.ts \
  packages/web/dsh-pmboard/tests/clause-coverage-gate.test.ts \
  packages/web/dsh-pmboard/tests/rtm-health.test.ts \
  packages/web/dsh-pmboard/tests/dive-gate-prompt.test.ts \
  packages/web/dsh-pmboard/tests/dive-session-driver-wiring.test.ts \
  packages/web/dsh-pmboard/tests/dive-round-driver.test.ts \
  packages/web/dsh-pmboard/tests/dive-manager-alignment.test.ts \
  packages/web/dsh-pmboard/tests/capture-hook.test.ts \
  packages/web/dsh-pmboard/tests/isolate-node-context.test.ts \
  packages/tools/reqboard/tests/rtm/triggers.test.ts
```

输出摘要：

```
 Test Files  21 passed (21)
      Tests  219 passed (219)
```

## T2 · FR-12 专项（bind 触发点）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
node_modules/.bin/vitest run packages/tools/reqboard/tests/rtm/triggers.test.ts
```

```
 Test Files  1 passed (1)
      Tests  14 passed (14)
```

（由 11 例增至 14 例：新增「bind 刷新集合恰为 rtm-lifecycle.yml」「先建后绑 source_session 随之一致」「空绑定不造假字段」。）

## T3 · FR-11 / FR-14 专项（Dive 两半）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
node_modules/.bin/vitest run \
  packages/web/dsh-pmboard/tests/dive-gate-prompt.test.ts \
  packages/web/dsh-pmboard/tests/dive-session-driver-wiring.test.ts \
  packages/web/dsh-pmboard/tests/dive-round-driver.test.ts \
  packages/web/dsh-pmboard/tests/dive-manager-alignment.test.ts
```

```
 Test Files  4 passed (4)
      Tests  44 passed (44)
```

`dive-gate-prompt.test.ts` 里与"有界重弹"直接相关的断言（TC-15）：
- 同一次等待（弹框在途）只弹 1 次；
- 冷却窗（5 分钟）内不重弹；产物指纹变化视为新一轮可立即弹；
- 上限 2 次后写台账 comment **恰好 1 条**并停手（3 次 idle 不再增长）。

## T4 · 修复前实机复现（FR-10 的现场证据）

在**已绑定需求**的本窗口（session-52f725ef）调 `reqboard_status`，得到：

```
tool "reqboard_status" returned invalid output: value is not lossless JSON
```

根因定位（`src/application/internal/rtm-health.ts`）：无失败记录时返回 `last_failure: undefined`（own property）——
`JSON.stringify` 静默丢键，但 PTC 绑定层的 lossless 校验会拦下。修法 = 无记录时**省略该键**，
并由 `tests/status-lossless.test.ts` 递归断言返回体无 `undefined` 值属性。

## T5 · 构建核验（改动真的进产物）

```bash
cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
pnpm build
# -> dist/index.mjs 1.15 MB；client 经 scripts/verify-client-build.mjs 检查通过；退出码 0
```

```bash
grep -c reqboard_task_move dist/index.mjs   # 25
grep -c reqboard_move      dist/index.mjs   # 22
```

> 注：运行中的 :13080 实例需重启才加载新产物（本仓既有语义）；重启前 `reqboard_status` 仍报旧错误。

## T6 · 台账读数（任务与 rollup）

```text
REQ-260927100007-b8ba  tasks 16  {"done":16}
需求状态：accepting（自动 rollup）
台账评论：[自动推进] implementing → accepting：全部 16 个实施任务已完成，自动进入验收
```

## T7 · 既有失败复核（非本需求引入）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
node_modules/.bin/vitest run --pool=forks packages/web/dsh-pmboard/tests/acceptance-criteria.test.ts
```

```
 Test Files  1 failed (1)
      Tests  1 failed | 36 passed (37)
 FAIL ... > 验收 4：老台账兼容加载 > expected 8 to be 7
```

- 该断言与本需求无关：HEAD 的 `REQBOARD_SCHEMA_VERSION` 已是 8（本需求**未动** schemaVersion，需求边界明确"不改台账 schemaVersion"）。
- 默认 threads 池下该文件另因 `process.chdir() is not supported in workers` 全红（vitest 1.x worker 限制）。

## T8 · 文档自检

```bash
cd /Users/yunpeng/pi-investment
python3 agent-dh/scripts/wiki_probe.py            # 现行页死链 30 条：全部既有（见 reviews/ 的 B4）
python3 agent-dh/scripts/docs_index.py --check     # OK：索引与文档一致
```

## T9 · 任务覆盖标注（covers）

> 每个任务卡对应**实际跑过的**测试文件（不是"声明覆盖"）。t-a1ecaa 是文档任务，由本文件 T8 + `reviews/acceptance-selfcheck.md` 自检覆盖，无单测。

| 任务 | 覆盖它的测试 | 锚点 |
|---|---|---|
| t-4b7697（FR-8 任务级收敛点） | `packages/web/dsh-pmboard/tests/task-transition-guard.test.ts` | 非法/人工门转移抛错且零副作用 |
| t-9785bb（FR-7 工具补齐） | `packages/web/dsh-pmboard/tests/apply-wiring.test.ts` | 期望工具集合含 reqboard_move / reqboard_task_move |
| t-8bce7d（MoveTask 契约） | `execute-task` / `lazy-expand` / `concurrency-limits` / `application/use-cases` 四文件 | 懒展开、父卡上限、task_card、done 凭证门、human_gate 映射 |
| t-29a9b8（FR-1/FR-2 批准即落库 + 响亮化） | `packages/web/dsh-pmboard/tests/confirm-settle-plan-persist.test.ts` | 批准后台账任务数 = 计划卡数；失败不推进 + pausedReason |
| t-4ed3cc（FR-3 完整性守卫） | `packages/web/dsh-pmboard/tests/advance-task-completeness-guard.test.ts` | 计划有卡/台账 0 卡 → 拒 + 修复指引 |
| t-4de551（FR-4 门禁提示） | `packages/web/dsh-pmboard/tests/clause-coverage-gate.test.ts` | 失败提示给两条可用路径 |
| t-722397（FR-5 返回体契约） | `packages/web/dsh-pmboard/tests/tools-schema.test.ts`、`contract-shapes.test.ts` | task_coverage 声明为 array |
| t-15d2d8（FR-6 RTM 刷新集合） | `packages/tools/reqboard/tests/rtm/triggers.test.ts` | task:status/task:report 含 rtm-decomposing.yml |
| t-4f717c（FR-9 挂起期停手） | `packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts` | pending 时写路径被拒、status/receipt 可用 |
| t-92c999（FR-10 lossless） | `packages/web/dsh-pmboard/tests/status-lossless.test.ts` | 递归无 undefined 值属性 |
| t-d73cec（FR-11 采集半零投递） | `dive-session-driver-wiring` / `capture-hook` / `isolate-node-context` | 连续两条人类消息 → 零投递；armed+active 才走 round 半 |
| t-2c852b（FR-12 绑定投影） | `packages/tools/reqboard/tests/rtm/triggers.test.ts` | bind 只刷新 rtm-lifecycle.yml；先建后绑一致 |
| t-0fad87（FR-13 证据路径推进） | `packages/web/dsh-pmboard/tests/confirm-evidence.test.ts` | 证据确认后同调用内推进 |
| t-08fcc2（FR-14 人工门弹框） | `packages/web/dsh-pmboard/tests/dive-gate-prompt.test.ts` | 门已满足未推进 → 弹推进框；有界重弹 |
| t-52999b（装配 stub 与期望集合） | `packages/web/dsh-pmboard/tests/apply-wiring.test.ts` | 装配不再抛 provide 错；期望集合对齐实际 17 个 |
| t-a1ecaa（同步文档） | `tests/verification-evidence.md` T8 + `reviews/acceptance-selfcheck.md` | wiki_probe / docs_index 自检 |

<!-- covers: t-4b7697 -->
<!-- covers: t-9785bb -->
<!-- covers: t-8bce7d -->
<!-- covers: t-29a9b8 -->
<!-- covers: t-4ed3cc -->
<!-- covers: t-4de551 -->
<!-- covers: t-722397 -->
<!-- covers: t-15d2d8 -->
<!-- covers: t-4f717c -->
<!-- covers: t-92c999 -->
<!-- covers: t-d73cec -->
<!-- covers: t-2c852b -->
<!-- covers: t-0fad87 -->
<!-- covers: t-08fcc2 -->
<!-- covers: t-52999b -->
<!-- covers: t-a1ecaa -->
