# t-2a1ea4 接口联调记录（REQ-260927121324-abde · 父卡「新增执行与迁移收敛的结构守卫单测」· 阶段 integrate）

> 验收标准：接口联调通过：给出请求样例与期望响应，实际返回与预期一致。
> 结论：**通过** —— 守卫契约 2 个接口面 / **12 例三方比对 12/12 MATCH，MISMATCH=0**（正向 8 例全绿 + 故障注入 4 例全红且逐条打印「文件:行号」）；父卡验收命令 2 文件 8 例通过；相关 token 回归 8 文件 49 例通过。
> 数据时点：全部命令 2026-09-27 15:02–15:03（CST），vitest v2.1.9，工作目录 `/Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard`。

## 1. 联调对象（接口面）

父卡 t-9b87a6 交付面 = 两条「写点只准在助手内」的源码扫描守卫：

| 编号 | 接口（代码位置） | 请求样例 | 期望响应语义 |
|---|---|---|---|
| I-1 | `tests/execution-token-guard.test.ts`（源扫描：src/**/*.ts 排除 application/internal/token-usage.ts） | 源码树 299 个 .ts（排除后 298） | `executions.push(` / `tokenUsage` 赋值零命中 → 全绿；命中 → 断言列表含「相对路径:第 N 行 · 式样 → 原文」 |
| I-2 | `tests/requirement-transition-guard.test.ts`（源扫描：src/application + src/http，排除 token-usage.ts） | 源码树 121 个 .ts（排除后 120） | `req.status` / `r.status` 直接赋值零命中 → 全绿；命中 → 同上格式报点 |

联调方式：① **正向**按真实源码树跑两个守卫；② **故障注入**在隔离副本（`/tmp/pmboard-guard-probe`，src 全量拷贝 + 两个守卫 + node_modules 软链）注入 4 处违规，验证守卫**真会变红**且定位准确；③ **独立交叉核查**用 grep/node 单行脚本复核守卫「干净」结论属实（防扫描器假绿）。探针副本已跑完即删，未留档、未改被测包 src。

## 2. 联调命令与输出摘要

正向（真实源码树）：

    $ npx vitest run tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts
     ✓ tests/requirement-transition-guard.test.ts (4 tests) 65ms
     ✓ tests/execution-token-guard.test.ts (4 tests) 124ms
     Test Files  2 passed (2) / Tests  8 passed (8)     ← VITEST_EXIT=0

故障注入（隔离副本，注入后）：

    $ npx vitest run tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts
     ❯ tests/requirement-transition-guard.test.ts (4 tests | 1 failed)
       × src/application 与 src/http 内无 req.status / r.status 直接赋值
     ❯ tests/execution-token-guard.test.ts (4 tests | 1 failed)
       × src 下（token-usage.ts 之外）无 executions.push( 与 tokenUsage 赋值
     Test Files  2 failed (2) / Tests  2 failed | 6 passed (8)    ← VITEST_EXIT=1
     （6 passed 含「扫描面非空」「收敛点仍在」「内建反例」三组守卫自身健康断言）

相关 token 回归（仅跑设计命令中已存在的文件；3 个尚未落盘的文件属 t-49d8d4 卡范围）：

    $ npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts tests/token-endpoint.test.ts tests/verdicts-and-rework.test.ts tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts
     Test Files  8 passed (8) / Tests  49 passed (49)            ← VITEST_EXIT=0

独立交叉核查：

    $ find src -name '*.ts' | wc -l                                  → 299
    $ find src/application src/http -name '*.ts' | wc -l             → 121
    $ grep -rn "executions.push(" src
      src/application/internal/token-usage.ts:113   （注释：声明纪律）
      src/application/internal/token-usage.ts:160   （openExecution 内，唯一写点）
    $ grep -rn "tokenUsage" src | grep -v internal/token-usage.ts
      → 仅读引用（req.tokenUsage?.byStage / e.tokenUsage === undefined）与类型声明（shared/protocol.ts:860/1075）
    $ node 单行脚本扫描 src/application+src/http 的 `.status =` 赋值（剔除行内注释）
      → 仅 2 处：application/internal/task-transition.ts:36（task.status = to，任务态，非需求态）
                 application/internal/token-usage.ts:291（req.status = to，收敛点本身）
    $ grep -rn "beginExecutionToken" src
      → token-usage.ts:159（openExecution 内部调用）—— 收敛 API 非死代码

## 3. 三方对照表（12 例）

| 编号 | 请求样例 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| P-1 | 真实 src（299 .ts） | execution-token-guard: 4 passed, violations=[] | 4 passed，violations=[] | MATCH |
| P-2 | 真实 src/application+src/http（121 .ts） | requirement-transition-guard: 4 passed, violations=[] | 4 passed，violations=[] | MATCH |
| P-3 | 扫描面统计 | I-1: allFiles=299, scanned=298；I-2: allFiles=121, scanned=120 | 同左（断言均含「排除项恰好命中一个文件」） | MATCH |
| P-4 | 收敛点自检 | token-usage.ts 含 openExecution / closeExecutions / task.executions.push(execution) / transitionRequirement / req.status = to | 同左（existsSync + toContain 全过） | MATCH |
| F-1 | 注入 `task.executions.push(execution)` @ src/__probe_a_violation.ts:2 | I-1 FAIL，条目 `src/__probe_a_violation.ts:第 2 行 · executions.push( → task.executions.push(execution)` | 逐字一致（见 §2 输出） | MATCH |
| F-2 | 注入 `execution.tokenUsage = 1` @ 同文件:3 | I-1 FAIL，条目 `src/__probe_a_violation.ts:第 3 行 · tokenUsage 赋值 → execution.tokenUsage = 1` | 逐字一致 | MATCH |
| F-3 | 注入 `req.status = to` @ src/application/__probe_b_violation.ts:2 | I-2 FAIL，条目 `src/application/__probe_b_violation.ts:第 2 行 · req.status 直接赋值 → req.status = to` | 逐字一致 | MATCH |
| F-4 | 注入 `r.status = to` @ 同文件:4 | I-2 FAIL，条目 `src/application/__probe_b_violation.ts:第 4 行 · r.status 直接赋值 → r.status = to` | 逐字一致 | MATCH |
| F-5 | 注入后两守卫的退出码 | 非零（红灯） | VITEST_EXIT=1 | MATCH |
| F-6 | 注入后「收敛点仍在」「扫描面非空」等健康断言 | 仍应通过（注入不应让守卫整体崩掉） | 6 passed | MATCH |
| X-1 | 手工 grep `executions.push(` 全 src | 仅收敛点 1 处实现 + 1 处注释 | 同左 | MATCH |
| X-2 | 手工扫描 application+http 的 `.status =` 赋值 | 需求态仅收敛点 token-usage.ts:291 一处 | 同左（另 1 处为 task.status） | MATCH |

> 说明：注入文件仅存在于隔离副本，真实包 `src/` 未新增/修改任何文件（见 §4 核查）。

## 4. 结构核查与残余观察

    $ rm -rf /tmp/pmboard-guard-probe        → 探针已清理（test -d → 不存在）
    $ git -C agent-dh status --porcelain packages/web/dsh-pmboard/tests/execution-token-guard.test.ts packages/web/dsh-pmboard/tests/requirement-transition-guard.test.ts
      ?? agent-dh/packages/web/dsh-pmboard/tests/execution-token-guard.test.ts
      ?? agent-dh/packages/web/dsh-pmboard/tests/requirement-transition-guard.test.ts
      → 两文件为研子卡 t-d108cf 新增（untracked）；本卡（联调）未新增/修改 src、tests 任何文件，
        本卡唯一落盘物 = 本证据文档
    $ cat vitest.config.ts                   → include: ['tests/**/*.test.ts']，两个守卫自动纳入 pnpm test

残余观察（**不影响本卡验收**，与卡片口径一致）：

1. 守卫为**逐行**匹配：跨行写法（`req\n  .status = to`、`task.executions\n  .push(e)`）不在覆盖范围。当前 src 无任何此类写法；卡片实施方案要求的正是「不含 `req.status = ` 字面」，故属已知边界而非偏差。
2. 守卫只认变量名 `req` / `r`（I-2）：改名后的直写（如 `target.status = to`）会漏。本期实测 application+http 内需求态直写仅收敛点 1 处，无改名残留；若要更强保证需 AST 级校验，超出本卡范围。
3. `design/test-cases.md` 的 7 文件验收命令中 `accept-verdicts-snapshot / rollup-snapshot / task-move-snapshot` 三个文件尚未落盘（属 t-49d8d4 卡），本卡只复跑已存在的 8 个文件。

## 5. 结论

- I-1/I-2 两个接口面**正向全绿、故障注入全红**：守卫既非「永不报警」的假绿，也非误报源（读引用/类型声明/比较/注释四类反例均不误报）。
- 12 例三方比对 **12/12 MATCH，MISMATCH=0**；报点格式严格为「文件:第 N 行 · 式样 → 原文」，满足卡片「违规时断言信息打印文件与行号」。
- 独立 grep/node 交叉核查与守卫判定一致，「唯一写入口」结论属实；`beginExecutionToken` 有真实调用方，收敛 API 非死代码。
- 未发现偏差，无需返工；残余观察 1–3 为已知边界，登记供复核/后续卡参考。
